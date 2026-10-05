import json
import re
import docker
from typing import Dict, Any, List
from src.shared_services.docker_sandbox import execute_in_container

async def compute_gitleaks_tier(container: docker.models.containers.Container, target_dir: str) -> int:
    """
    Computes timeout tier logic evaluating highest duration between .git 
    folder size vs working tree size, as required by TRD Feature 7.
    """
    # 1. Get working tree size per same algorithm as Semgrep metric
    exit_code, tree_out = await execute_in_container(container, f"du -sb --exclude={target_dir}/.git {target_dir}")
    tree_size = int(tree_out.split()[0].strip()) if exit_code == 0 and tree_out.strip() else 0
    tree_mb = tree_size / (1024 * 1024)
    
    exit_code, count_out = await execute_in_container(container, f"find {target_dir} -path '*/.git/*' -prune -o -type f -print | wc -l")
    file_count = int(count_out.strip()) if exit_code == 0 and count_out.strip() else 0

    tree_tier = 300
    if tree_mb > 50.0 or file_count > 2000:
        tree_tier = 1800
    elif tree_mb >= 10.0 or file_count >= 500:
        tree_tier = 900

    # 2. Get .git size explicitly
    exit_code, git_out = await execute_in_container(container, f"du -sb {target_dir}/.git")
    git_size = int(git_out.split()[0].strip()) if exit_code == 0 and git_out.strip() else 0
    git_mb = git_size / (1024 * 1024)

    git_tier = 300
    if git_mb > 50.0:
        git_tier = 1800
    elif git_mb >= 10.0:
        git_tier = 900

    return max(tree_tier, git_tier)

def redact_snippet(raw_lines: List[str], min_line: int, start_line: int, end_line: int, start_col: int, end_col: int, rule_id: str) -> str:
    """
    Applies the triple-masking mandated by TRD Feature 7:
    1. Replaces exact coordinates in the text with a [REDACTED ...] placeholder.
    2. Runs generic regex masks blindly over the rest of the 51-line string.
    """
    # Coordinate Replacement bounds logic
    for i in range(start_line, end_line + 1):
        idx = i - min_line
        if 0 <= idx < len(raw_lines):
            line_str = raw_lines[idx]
            
            # Substring extraction to determine if looks_placeholder
            target_val = ""
            if i == start_line and i == end_line:
                # Single line secret
                if start_col - 1 < len(line_str) and end_col - 1 <= len(line_str):
                    target_val = line_str[start_col-1:end_col-1]
            
            looks_placeholder = False
            if target_val:
                lower = target_val.lower()
                looks_placeholder = any(sub in lower for sub in ["example", "your", "xxxx", "test", "dummy", "placeholder", "xxx"])
            
            placeholder = f"[REDACTED rule={rule_id} len={len(target_val) if target_val else 'X'} looks_placeholder={'true' if looks_placeholder else 'false'}]"
            
            if i == start_line and i == end_line:
                prefix = line_str[:start_col-1]
                suffix = line_str[end_col-1:]
                raw_lines[idx] = prefix + placeholder + suffix
            elif i == start_line:
                raw_lines[idx] = line_str[:start_col-1] + placeholder
            elif i == end_line:
                raw_lines[idx] = placeholder + line_str[end_col-1:]
            else:
                raw_lines[idx] = placeholder
                
    joined_snippet = "\n".join(raw_lines)
    
    # 3. Independent regex blanket masking across the entire 51 line window as a safeguard
    joined_snippet = re.sub(r'(sk-[a-zA-Z0-9]{32,100})', lambda m: f"[REDACTED rule=openai-key len={len(m.group(1))} looks_placeholder=false]", joined_snippet, flags=re.IGNORECASE)
    joined_snippet = re.sub(r'(sk-ant-[a-zA-Z0-9\-_]{32,100})', lambda m: f"[REDACTED rule=anthropic-key len={len(m.group(1))} looks_placeholder=false]", joined_snippet, flags=re.IGNORECASE)
    joined_snippet = re.sub(r'(gsk_[a-zA-Z0-9]{32,90})', lambda m: f"[REDACTED rule=groq-key len={len(m.group(1))} looks_placeholder=false]", joined_snippet, flags=re.IGNORECASE)
    
    return joined_snippet

async def run_gitleaks(container: docker.models.containers.Container, target_dir: str, job_id: str, db_client) -> bool:
    """
    Executes offline Gitleaks Secret scan running in parallel against codebase (+.git),
    extracting 51 lines of context and parsing findings securely without retaining literal secrets.
    """
    timeout_s = await compute_gitleaks_tier(container, target_dir)
    
    # --redact hides secrets from the raw gitleaks JSON output itself (TRD requirement #2)
    # --no-git skips git diff scanning and treats the folder as a blind directory if .git doesn't exist,
    # but Gitleaks naturally reads .git if present.
    cmd = (f"gitleaks detect --source {target_dir} --config /opt/gitleaks.toml "
           f"--report-format json --report-path /tmp/secrets.json --redact --exit-code 0")
           
    try:
        # We explicitly suppress Gitleaks exit 1 (findings present) by passing --exit-code 0 so only engine crashes halt execution
        exit_code, _ = await execute_in_container(container, cmd, timeout_seconds=timeout_s)
    except TimeoutError:
        # TRD: silently incomplete scan is worse than a failed job.
        db_client.table("scan_jobs").update({"status": "failed", "failure_code": "timeout_exceeded"}).eq("id", job_id).execute()
        return False
        
    if exit_code != 0:
        db_client.table("scan_jobs").update({"status": "failed", "failure_code": "scanner_crashed"}).eq("id", job_id).execute()
        return False
        
    # Read the JSON generated securely
    code, json_bytes = await execute_in_container(container, "cat /tmp/secrets.json")
    if code != 0 or not json_bytes.strip():
        results = []
    else:
        try:
            results = json.loads(json_bytes.decode('utf-8', errors='ignore'))
        except json.JSONDecodeError:
            db_client.table("scan_jobs").update({"status": "failed", "failure_code": "scanner_crashed"}).eq("id", job_id).execute()
            return False

    mapped_findings = []
    for finding in results:
        file_path = finding.get("File", "")
        
        # Ensure path is relative
        if file_path.startswith(target_dir):
            file_path = file_path[len(target_dir):]
        if file_path.startswith("/"):
            file_path = file_path[1:]
            
        start_line = finding.get("StartLine", 1)
        end_line = finding.get("EndLine", 1)
        start_col = finding.get("StartColumn", 1)
        end_col = finding.get("EndColumn", 1)
        rule_id = finding.get("RuleID", "unknown")
        
        # TRD requires capturing 25 lines before & 25 lines after for context
        min_line = max(1, start_line - 25)
        max_line = start_line + 25
        
        # Read targeted block safely
        grab_cmd = f"sed -n '{min_line},{max_line}p' {target_dir}/{file_path}"
        r_code, r_out = await execute_in_container(container, grab_cmd)
        if r_code != 0:
            continue
            
        raw_lines = r_out.decode('utf-8', errors='ignore').splitlines()
        
        # Coordinate Replacement
        clean_snippet = redact_snippet(raw_lines, min_line, start_line, end_line, start_col, end_col, rule_id)
        
        mapped_findings.append({
            "category": "secret",
            "rule": rule_id,
            "file": file_path,
            "line": start_line,
            "snippet": clean_snippet,
            "severity_level": "critical"
        })
        
    record = {
        "scan_job_id": job_id,
        "scanner_type": "gitleaks",
        "status": "completed",
        "raw_output": {"findings": mapped_findings},
        "finding_count": len(mapped_findings),
        "ruleset_version": "mvp-baked"
    }
    
    db_client.table("scanner_runs").insert(record).execute()
    return True
