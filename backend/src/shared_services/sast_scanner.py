import json
import docker
from src.shared_services.docker_sandbox import execute_in_container

async def compute_semgrep_tier_and_prepare(container: docker.models.containers.Container, target_dir: str) -> int:
    """
    Computes timeout tier logic and creates large file exclusions per TRD.
    Returns the appropriate isolation timeout in seconds.
    """
    # Feature 6 requires excluding individual source files > 2MB.
    # Semgrep native excludes operate efficiently by reading an ignore file if specified,
    # or passing arguments. For scale, we write to an ignore file directly inside the boundary!
    await execute_in_container(
        container, 
        f"find {target_dir} -type f -size +2M > {target_dir}/.semgrepignore && echo '.git' >> {target_dir}/.semgrepignore"
    )
    
    # Calculate bytes via `du` excluding .git
    exit_code, du_out = await execute_in_container(container, f"du -sb --exclude={target_dir}/.git {target_dir}")
    size_bytes = 0
    if exit_code == 0 and du_out.strip():
        size_bytes = int(du_out.split()[0].strip())
    size_mb = size_bytes / (1024 * 1024)
        
    # Calculate file count precisely excluding .git
    exit_code, count_out = await execute_in_container(container, f"find {target_dir} -path '*/.git/*' -prune -o -type f -print | wc -l")
    file_count = 0
    if exit_code == 0 and count_out.strip():
        file_count = int(count_out.strip())
        
    # Evaluate TRD threshold bands. Wait time is allocated specifically.
    if size_mb > 50.0 or file_count > 2000:
        return 1800  # Large
    elif size_mb >= 10.0 or file_count >= 500:
        return 900   # Medium
    else:
        return 300   # Small

async def run_semgrep(container: docker.models.containers.Container, target_dir: str, job_id: str, db_client) -> bool:
    """
    Executes offline Semgrep SAST scan directly in the provided sandbox context,
    enforcing dynamic timeouts and recording raw JSON format outputs.
    """
    timeout_s = await compute_semgrep_tier_and_prepare(container, target_dir)
    
    # Write output directly to a file and suppress stderr to avoid corrupted JSON from merged TTY streams
    cmd = (
        f"semgrep scan --config p/owasp-top-ten --config p/default "
        f"--config p/cwe-top-25 --config p/security-audit --config p/secure-defaults --config p/ci "
        f"--config p/javascript --config p/typescript --config p/react --config p/python "
        f"--config /opt/semgrep/ai_rules.yaml --json {target_dir} --quiet > /tmp/sast.json 2>/dev/null"
    )
    
    try:
        exit_code, _ = await execute_in_container(container, cmd, timeout_seconds=timeout_s)
    except TimeoutError:
        # Halt precisely on execution time violation
        db_client.table("scan_jobs").update({"status": "failed", "failure_code": "timeout_exceeded"}).eq("id", job_id).execute()
        return False
        
    # Semgrep native exit code specification:
    # 0 = No findings, 1 = Findings present, ≥2 = Engine Failure
    if exit_code not in (0, 1): 
        db_client.table("scan_jobs").update({"status": "failed", "failure_code": "scanner_crashed"}).eq("id", job_id).execute()
        return False
        
    try:
        # Read the generated JSON securely, same pattern as gitleaks
        code, raw_output = await execute_in_container(container, "cat /tmp/sast.json")
        if code != 0:
            raise json.JSONDecodeError("Could not read /tmp/sast.json", "", 0)
        # Semgrep prints logs headers often before JSON. We need to parse strictly from `{` to end.
        if isinstance(raw_output, bytes):
            out_str = raw_output.decode('utf-8')
        else:
            out_str = raw_output
        
        json_start = out_str.find('{')
        if json_start == -1:
            raise json.JSONDecodeError("No JSON object could be decoded", out_str, 0)
        
        results = json.loads(out_str[json_start:])
    except json.JSONDecodeError:
        db_client.table("scan_jobs").update({"status": "failed", "failure_code": "scanner_crashed"}).eq("id", job_id).execute()
        return False
        
    # Transform native severities explicitly as required by TRD-01 Section 6 mapping mechanism
    mapped_findings = []
    finding_count = 0
    
    for finding in results.get("results", []):
        meta_sev = finding.get("extra", {}).get("severity", "").upper()
        severity = "low"
        if meta_sev == "ERROR":
            severity = "high"
        elif meta_sev == "WARNING":
            severity = "medium"
            
        finding["extra"]["normalized_severity"] = severity
        mapped_findings.append(finding)
        finding_count += 1
        
    # Encapsulate to scanner_runs independent relationship mapping ensuring TRD integrity 
    record = {
        "scan_job_id": job_id,
        "scanner_type": "semgrep",
        "status": "completed",
        "raw_output": {"findings": mapped_findings},
        "finding_count": finding_count,
        "ruleset_version": "mvp-baked"
    }
    
    db_client.table("scanner_runs").insert(record).execute()
    return True
