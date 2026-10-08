import asyncio
from src.shared_services.redis import redis_settings
from src.tasks.github_sandbox import start_github_clone_sandbox
from src.tasks.liveurl_scanner import start_liveurl_scan

async def startup(ctx):
    """
    Hook to initialize external resources once globally for the worker.
    """
    print("ARQ Worker Starting. Enforcing max_jobs=50 concurrency cap.")

async def shutdown(ctx):
    """
    Hook to tear down external capabilities cleanly.
    """
    print("ARQ Worker shutting down cleanly.")

# ARQ worker configuration class
class WorkerSettings:
    functions = [start_github_clone_sandbox, start_liveurl_scan]
    redis_settings = redis_settings
    on_startup = startup
    on_shutdown = shutdown
    
    # TRD-01 Feature 3 Constraint: strict platform-wide ceiling of 50 concurrent jobs
    max_jobs = 50
