import asyncio
import docker
from typing import Tuple, Dict

# Maintain a localized client connecting to the system Docker socket
client = None

def get_docker_client():
    global client
    if client is None:
        try:
            client = docker.from_env()
        except Exception:
            raise RuntimeError("Docker client is not available. Please ensure Docker is running.")
    return client

async def provision_container(job_id: str) -> docker.models.containers.Container:
    """
    Provisions a fresh, isolated ephemeral container for the scan job.
    Uses asyncio.to_thread to prevent blocking the async worker loop.
    """
    docker_client = get_docker_client()
        
    container_name = f"scan-sandbox-{job_id}"
    
    # Run container detached using the pre-built sandbox image
    def _run_container():
        return docker_client.containers.run(
            "ai-security-scanner-sandbox:latest",
            name=container_name,
            detach=True,
            # We constrain the environment so it can't consume the host entirely, though
            # TRD-01 MVP focuses purely on business logic caps (like 500MB clone disk size)
            mem_limit="1g",
            cpu_quota=100000,
            network_mode="bridge"  # minimal bridge network for outbound clone access
        )

    # Wrap the synchronous docker call in a thread
    container = await asyncio.to_thread(_run_container)
    return container

async def execute_in_container(
    container: docker.models.containers.Container, 
    command: str,
    timeout_seconds: int = 120
) -> Tuple[int, bytes]:
    """
    Executes a shell command inside the provisioned container asynchronously.
    Enforces the provided timeout (TRD-01 defines 120s for clone ops).
    Returns (exit_code, output).
    """

    def _exec_start():
        # docker SDK exec_run blocks. We use it to run arbitrary shell commands.
        exec_instance = container.client.api.exec_create(
            container.id, 
            cmd=["/bin/sh", "-c", command],
            stdout=True,
            stderr=True
        )
        return container.client.api.exec_start(exec_instance["Id"]), exec_instance["Id"]

    def _inspect(exec_id):
        return container.client.api.exec_inspect(exec_id)

    # 1. Start execution
    output_stream, exec_id = await asyncio.to_thread(_exec_start)

    # 2. Monitor execution with timeout and heartbeat
    start_time = asyncio.get_event_loop().time()
    
    while True:
        inspect_data = await asyncio.to_thread(_inspect, exec_id)
        if not inspect_data["Running"]:
            # Finished execution
            exit_code = inspect_data["ExitCode"]
            return exit_code, output_stream
        
        # Check timeout
        if asyncio.get_event_loop().time() - start_time > timeout_seconds:
            # We cannot easily kill a specific exec instance in Docker trivially, 
            # but raising an exception here will trigger the caller's finally block to kill the WHOLE container.
            raise TimeoutError(f"Command exceeded {timeout_seconds}s timeout boundary.")
            
        await asyncio.sleep(0.5)

async def check_directory_size_mb(container: docker.models.containers.Container, path: str) -> float:
    """
    Measures the disk usage of a directory inside the container in MegaBytes.
    """
    code, output = await execute_in_container(container, f"du -sm {path} | awk '{{print $1}}'")
    if code != 0:
        return 0.0 # Path might not exist yet or failed
    try:
        return float(output.decode().strip())
    except ValueError:
        return 0.0

async def teardown_container(container: docker.models.containers.Container):
    """
    Unconditionally forces the destruction of the container and its anonymous volumes.
    This fulfills the TRD "Guaranteed Cleanup" rule.
    """
    def _destroy():
        try:
            # Force stops and removes the container, throwing away associated volumes
            container.remove(force=True, v=True)
        except docker.errors.NotFound:
            pass # Already removed somehow, safe to ignore
        except Exception as e:
            # Log cleanup failures, this is structurally critical
            print(f"CRITICAL: Failed to teardown container {container.id}: {e}")
            
    await asyncio.to_thread(_destroy)
