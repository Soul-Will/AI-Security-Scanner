import os
import docker
from typing import List, Dict
from src.shared_services.docker_sandbox import execute_in_container

# Feature 5: Define the 1:1 map between manifest filename and canonical DB dependency_ecosystem ENUM value.
MANIFEST_MAPPING = {
    "package.json": "npm",
    "requirements.txt": "pip",
    "pom.xml": "maven"
}

async def detect_stacks(container: docker.models.containers.Container, target_dir: str, job_id: str, db_client) -> List[Dict]:
    """
    Recursively traverse the cleaned workspace up to 4 directory levels deep
    to locate manifest files indicative of ecosystem dependencies.
    Logs each unique instance into `detected_stacks`.
    """
    
    # Construct exact `-name` match chain for find
    name_args = " -o ".join([f'-name "{manifest}"' for manifest in MANIFEST_MAPPING.keys()])
    
    # Rule: Max directory depth of 4 levels
    command = f"find {target_dir} -maxdepth 4 -type f \\( {name_args} \\)"
    
    exit_code, output = await execute_in_container(container, command)
    if exit_code != 0:
        # Failsafe; if find throws an error, assume broken structure, don't crash the whole run.
        return []

    lines = [line.strip() for line in output.decode('utf-8').split('\n') if line.strip()]
    
    detected_stacks = []
    
    for abs_path in lines:
        filename = os.path.basename(abs_path)
        if filename not in MANIFEST_MAPPING:
            continue
            
        ecosystem = MANIFEST_MAPPING[filename]
        
        # Strip absolute prefix ensuring a clean relative path explicitly (Linux-formatted sandbox path)
        rel_path = abs_path
        if abs_path.startswith(target_dir):
            rel_path = abs_path[len(target_dir):].lstrip('/')
            if not rel_path:
                rel_path = filename
        
        detected_stacks.append({
            "scan_job_id": job_id,
            "ecosystem": ecosystem,
            "manifest_path": rel_path
        })
        
    if detected_stacks:
        try:
            # Upsert into detected_stacks to cleanly honor the UNIQUE(scan_job_id, manifest_path) constraint
            db_client.table("detected_stacks").upsert(
                detected_stacks,
                on_conflict="scan_job_id,manifest_path"
            ).execute()
        except Exception as e:
            print(f"Stack detection DB persistence error (likely duplicate or schema format error): {str(e)}")
            
    return detected_stacks
