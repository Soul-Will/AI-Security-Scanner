import subprocess
import tempfile
import shutil
from pathlib import Path

def clone_and_scan_github(repo_url: str, scan_id: str) -> dict:
    # 1. Create temp directory
    temp_dir = tempfile.mkdtemp(prefix=f"scan_{scan_id}_")
    
    try:
        # 2. Clone the repo
        clone_result = subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, temp_dir],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if clone_result.returncode != 0:
            return {
                "status": "failed",
                "error": clone_result.stderr.strip()
                or "Git clone failed",
            }
        # 3. Run Semgrep
        result = subprocess.run(
            ["semgrep", "--json", "--config=auto", temp_dir],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

        if result.returncode > 1:
            return {
                "status": "failed",
                "error": result.stderr.strip()
                or "Semgrep scan failed",
            }

        if not result.stdout.strip():
            return {
                "status": "failed",
                "error": result.stderr.strip()
                or "Semgrep returned no JSON output",
            }
        # 4. Parse results
        import json
        findings = json.loads(result.stdout)
        
        return {
            "status": "completed",
            "total_findings": len(findings.get("results", [])),
            "findings": findings.get("results", [])[:10]  # Limit for now
        }
        
    except json.JSONDecodeError as error:
        return {
            "status": "failed",
            "error": f"Invalid Semgrep JSON output: {error}",
        }

    except FileNotFoundError as error:
        return {
            "status": "failed",
            "error": (
                f"Required command was not found: {error.filename}. "
                "Make sure Git and Semgrep are installed and available "
                "on PATH."
            ),
        }

    except Exception as error:
        return {
            "status": "failed",
            "error": str(error),
        }

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)