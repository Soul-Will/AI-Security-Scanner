import asyncio
from typing import List
import docker
from src.shared_services.docker_sandbox import execute_in_container

# TRD-01 Feature 4 Baseline set constraints.
# IMPORTANT: .git is specifically excluded from this list per the TRD.
JUNK_DIRS: List[str] = [
    "node_modules", 
    "__pycache__", 
    "venv", 
    "build", 
    "dist", 
    ".next", 
    "target", 
    ".gradle", 
    "vendor"
]

class PreprocessingError(Exception):
    pass

async def exclude_junk_folders(container: docker.models.containers.Container, target_dir: str) -> bool:
    """
    Strips non-essential junk directories from the repository to prevent scanner overload.
    Enforces a strict 3-attempt linear backoff retry (1s, 2s, 3s) on permission faults.
    """
    
    # Construct the find command. 
    # Use -prune so find doesn't attempt to traverse into directories it is concurrently deleting.
    find_names = " -o ".join([f'-name "{d}"' for d in JUNK_DIRS])
    command = f"find {target_dir} -type d \\( {find_names} \\) -prune -exec rm -rf {{}} +"
    
    # Linear backoff schedule defined by TRD exactly:
    backoff_schedule = [1, 2, 3]
    
    attempts = 0
    # Maximum 1 initial try + 3 retries = 4 total attempts
    total_allowed_attempts = len(backoff_schedule)
    
    while attempts <= total_allowed_attempts:
        exit_code, output = await execute_in_container(container, command)
        
        if exit_code == 0:
            # Successfully stripped junk or it was a no-op (no junk found)
            return True
            
        # If we failed but have attempts remaining, wait according to the schedule and try again
        if attempts < total_allowed_attempts:
            await asyncio.sleep(backoff_schedule[attempts])
            attempts += 1
        else:
            # We have exhausted the 3-attempt backoff schedule. 
            raise PreprocessingError("Failed to delete junk folders due to persistent sandbox permission issues.")
            
    return False
