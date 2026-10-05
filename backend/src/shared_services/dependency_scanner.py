import posixpath
import json
import asyncio
from datetime import datetime, timezone
import docker
from src.shared_services.docker_sandbox import execute_in_container

# TRD-01 Feature 8 mappings
NPM_SEVERITY_MAPPING = {
    "info": "info",
    "low": "low",
    "moderate": "medium",
    "high": "high",
    "critical": "critical"
}

async def run_dependency_scanners(container: docker.models.containers.Container, target_dir: str, job_id: str, db_client, detected_stacks: list):
    """
    Run dependency scanners (npm audit, pip-audit) on the detected stacks.
    Each run has a static 120s max execution timeout.
    """
    if not detected_stacks:
        return
        
    tasks = []
    
    for stack in detected_stacks:
        ecosystem = stack.get("ecosystem")
        manifest_path = stack.get("manifest_path")
        
        if ecosystem == "maven":
            # TRD-01 Feature 8: Java dependency scanning is out of scope. Write Info-level finding.
            _insert_bypass_finding(db_client, job_id, ecosystem, manifest_path)
            
        elif ecosystem == "npm":
            tasks.append(_run_npm_audit(container, target_dir, manifest_path, job_id, db_client))
            
        elif ecosystem == "pip":
            tasks.append(_run_pip_audit(container, target_dir, manifest_path, job_id, db_client))

    if tasks:
        # Run independent manifests concurrently
        await asyncio.gather(*tasks)

async def _run_npm_audit(container, target_dir, manifest_path, job_id, db_client):
    started_at = datetime.now(timezone.utc).isoformat()
    manifest_dir = posixpath.dirname(posixpath.join(target_dir, manifest_path))
    
    # We redirect the output to a file and read it back, ignoring stderr to prevent JSON pollution
    cmd = f"cd {manifest_dir} && npm audit --json > /tmp/npm_audit.json 2>/tmp/npm_err.txt; cat /tmp/npm_audit.json; echo '!!!:::STDERR:::!!!'; cat /tmp/npm_err.txt"
    
    try:
        exit_code, output_bytes = await execute_in_container(container, cmd, timeout_seconds=120)
        output_str = output_bytes.decode('utf-8').strip()
        
        # Split stdout and stderr
        parts = output_str.split('!!!:::STDERR:::!!!')
        stdout_str = parts[0].strip()
        stderr_str = parts[1].strip() if len(parts) > 1 else ""
        
        if not stdout_str:
            _record_scanner_run(db_client, job_id, "npm_audit", "failed", started_at, error_message=f"npm audit produced no output. Stderr: {stderr_str}")
            return
            
        start_idx = stdout_str.find('{')
        if start_idx == -1:
            raise ValueError(f"No JSON payload found in output. Stderr: {stderr_str}")
        parsed_output = json.loads(stdout_str[start_idx:])

        vuln_count = 0
        metadata = parsed_output.get("metadata", {})
        if "vulnerabilities" in metadata:
            vuln_count = metadata["vulnerabilities"].get("total", 0)
            
        _record_scanner_run(db_client, job_id, "npm_audit", "completed", started_at, raw_output=parsed_output, finding_count=vuln_count)
            
    except TimeoutError as e:
        _record_scanner_run(db_client, job_id, "npm_audit", "failed", started_at, error_message=f"Timeout: {str(e)}")
    except json.JSONDecodeError as e:
        _record_scanner_run(db_client, job_id, "npm_audit", "failed", started_at, error_message=f"JSON parsing failed: {str(e)}. Output: {output_str[:100]}")
    except Exception as e:
        _record_scanner_run(db_client, job_id, "npm_audit", "failed", started_at, error_message=f"Error: {str(e)}")

async def _run_pip_audit(container, target_dir, manifest_path, job_id, db_client):
    started_at = datetime.now(timezone.utc).isoformat()
    abs_manifest = posixpath.join(target_dir, manifest_path)
    
    # Send JSON parsing safely via a tmp file to avoid stderr pollution
    cmd = f"pip-audit -r {abs_manifest} -f json > /tmp/pip_audit.json 2>/tmp/pip_err.txt; cat /tmp/pip_audit.json; echo '!!!:::STDERR:::!!!'; cat /tmp/pip_err.txt"
    
    try:
        exit_code, output_bytes = await execute_in_container(container, cmd, timeout_seconds=120)
        output_str = output_bytes.decode('utf-8').strip()
        
        # Split stdout and stderr
        parts = output_str.split('!!!:::STDERR:::!!!')
        stdout_str = parts[0].strip()
        stderr_str = parts[1].strip() if len(parts) > 1 else ""
        
        if not stdout_str:
            _record_scanner_run(db_client, job_id, "pip_audit", "failed", started_at, error_message=f"pip-audit produced no output. Stderr: {stderr_str}")
            return

        start_idx = stdout_str.find('[')
        start_idx_obj = stdout_str.find('{')
        
        valid_start = start_idx if start_idx != -1 else start_idx_obj
        if start_idx != -1 and start_idx_obj != -1:
            valid_start = min(start_idx, start_idx_obj)
            
        if valid_start == -1:
            raise ValueError(f"No JSON payload found in output. Stderr: {stderr_str}")
            
        end_char = ']' if stdout_str[valid_start] == '[' else '}'
        end_idx = stdout_str.rfind(end_char)
        
        if end_idx == -1 or end_idx < valid_start:
            raise ValueError("Malformed JSON boundaries")
            
        parsed_output = json.loads(stdout_str[valid_start:end_idx+1])
        
        finding_count = 0
        if isinstance(parsed_output, list):
            for dep in parsed_output:
                finding_count += len(dep.get("vulns", []))
        elif isinstance(parsed_output, dict):
            # newer pip-audit schema version
            deps = parsed_output.get("dependencies", [])
            for dep in deps:
                finding_count += len(dep.get("vulns", []))
                
        _record_scanner_run(db_client, job_id, "pip_audit", "completed", started_at, raw_output=parsed_output, finding_count=finding_count)
            
    except TimeoutError as e:
        _record_scanner_run(db_client, job_id, "pip_audit", "failed", started_at, error_message=f"Timeout: {str(e)}")
    except json.JSONDecodeError as e:
        _record_scanner_run(db_client, job_id, "pip_audit", "failed", started_at, error_message=f"JSON parsing failed: {str(e)}. Output: {output_str[:100]}")
    except Exception as e:
        _record_scanner_run(db_client, job_id, "pip_audit", "failed", started_at, error_message=f"Error: {str(e)}")


def _record_scanner_run(db_client, job_id, scanner_type, status, started_at, raw_output=None, finding_count=0, error_message=None):
    completed_at = datetime.now(timezone.utc).isoformat()
    
    run_data = {
        "scan_job_id": job_id,
        "scanner_type": scanner_type,
        "status": status,
        "raw_output": raw_output,
        "finding_count": finding_count,
        "error_message": error_message,
        "started_at": started_at,
        "completed_at": completed_at
    }
    
    try:
        db_client.table("scanner_runs").insert(run_data).execute()
    except Exception as e:
        print(f"Failed to record {scanner_type} run: {str(e)}")

def _insert_bypass_finding(db_client, job_id, ecosystem, manifest_path):
    try:
        res = db_client.table("findings").insert({
            "scan_job_id": job_id,
            "finding_type": "dependency_risk",
            "file_path": manifest_path,
            "severity": "info",
            "classification": "unverified",
            "explanation": "Java dependency scanning is not yet supported in this version"
        }).execute()
        
        if res.data:
            finding_id = res.data[0]['id']
            
            db_client.table("finding_dependency_details").insert({
                "finding_id": finding_id,
                "dependency_name": "pom.xml",
                "ecosystem": "maven"
            }).execute()
            
    except Exception as e:
        print(f"Failed to record bypass finding for {ecosystem}: {str(e)}")
