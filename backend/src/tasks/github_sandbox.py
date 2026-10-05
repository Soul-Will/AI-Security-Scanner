import os
from arq.worker import Retry
from src.shared_services.db import get_supabase_client
from src.shared_services.docker_sandbox import provision_container, execute_in_container, teardown_container, check_directory_size_mb

# We rely on Supabase singleton to bypass RLS via service role
supabase = get_supabase_client()

async def sync_job_status(job_id: str, new_status: str, failure_code: str = None, failure_reason: str = None):
    """Utility to safely transition state in the DB."""
    update_data = {"status": new_status}
    if failure_code:
        # Assuming there is a details/failure code mechanism. 
        # TRD doesn't explicitly mandate a specific failure column outside of `status='failed'`,
        # but says "failure_code = resource_exhausted".
        update_data["failure_code"] = failure_code
    if failure_reason:
        update_data["failure_reason"] = failure_reason
    supabase.table("scan_jobs").update(update_data).eq("id", job_id).execute()

async def start_github_clone_sandbox(
    ctx, 
    job_id: str,
    user_id: str, 
    repo_url: str, 
    owner: str, 
    repo: str, 
    visibility: str, 
    pat_supplied: bool
):
    """
    Feature 3: Secure Cloning Sandbox Implementation.
    """
    redis = ctx["redis"]
    
    # 1. Enforce Per-User Concurrency (TRD-01 Feature 3 - 2 concurrent jobs cap)
    active_redis_key = f"user_active_jobs:{user_id}"
    
    # Simple atomic lock mechanism using incr (assumes a reliable decrement later)
    # A true persistent system might query the postgres database here for robust tracking
    active_count = await redis.incr(active_redis_key)
    if active_count == 1:
        # First assignment, let's put an expiry to avoid zombie locks over long term
        await redis.expire(active_redis_key, 3600)
        
    if active_count > 2:
        await redis.decr(active_redis_key)
        # 10s soft-deferral logic enforcing backpressure. User does not receive a rejection!
        raise Retry(defer=10)
        
    container = None
    pat = None
    
    try:
        # State: processing -> preparing (per DB ENUM)
        await sync_job_status(job_id, "preparing")
        
        # Pull PAT from redis queue context if private
        if pat_supplied:
            pat_bytes = await redis.get(f"job_pat:{job_id}")
            if not pat_bytes:
                # PAT expired during backpressure / wait times!
                # TRD Feature 2 explicitly mandates 'auth_failed' and status 'rejected' 
                # (since container isn't provisioned yet, we use rejected)
                await sync_job_status(job_id, "rejected", failure_code="auth_failed")
                return
            pat = pat_bytes.decode('utf-8')
        
        # 2. Provision isolated container
        try:
            container = await provision_container(job_id)
        except Exception as e:
            await sync_job_status(job_id, "failed", failure_code="internal_error", failure_reason=f"Provisioning failed: {str(e)}")
            return
            
        await sync_job_status(job_id, "cloning")
        
        # 3. Construct protected clone URL
        # We must never log this URL. 
        clone_url = repo_url
        if pat:
            # We inject credentials inline. (https://oauth2:PAT@github.com/...)
            clone_url = clone_url.replace("https://", f"https://oauth2:{pat}@")
            
        # 4. Clone Operation inside the ephemeral boundary
        target_dir = f"/tmp/scan-job-{job_id}"
        clone_cmd = f"git clone {clone_url} {target_dir}"
        
        try:
            # Enforce the strict 120s timeout boundary
            exit_code, output = await execute_in_container(container, clone_cmd, timeout_seconds=120)
            
            if exit_code != 0:
                # E.g. clone failure due to wrong token scope or repo disappearance.
                await sync_job_status(job_id, "failed", failure_code="auth_failed" if pat else "upstream_unavailable")
                return
                
        except TimeoutError:
            # Exceeded the 120-second timeout!
            await sync_job_status(job_id, "failed", failure_code="timeout_exceeded")
            return
            
        # 5. Measure resulting disk footprint
        directory_mb = await check_directory_size_mb(container, target_dir)
        if directory_mb > 500.0:
            # Exceeded the 500MB Size limit!
            await sync_job_status(job_id, "failed", failure_code="resource_exhausted")
            return
            
        # SUCCESS on Feature 3
        # Start Feature 4: Pre-Processing (Junk File Exclusion)
        await sync_job_status(job_id, "extracting")
        from src.shared_services.preprocessor import exclude_junk_folders, PreprocessingError
        
        try:
            await exclude_junk_folders(container, target_dir)
        except PreprocessingError as e:
            # If all 3 linear backoff retries fail, TRD explicitly mandates internal_error
            await sync_job_status(job_id, "failed", failure_code="internal_error", failure_reason=str(e))
            return
            
        # Start Feature 5: Pre-Processing (Technology Stack Detection)
        from src.shared_services.stack_detector import detect_stacks
        from src.shared_services.db import get_supabase_client
        # get fresh DB client since ARQ worker scopes might differ if threaded
        db_client = get_supabase_client()
        detected = await detect_stacks(container, target_dir, job_id, db_client)
        print(f"Job {job_id} stack detection found {len(detected)} manifests.")
            
        # Start Feature 6, Feature 7 & Feature 8: SAST Scanning, Secret Detection & SCA
        await sync_job_status(job_id, "scanning")
        import asyncio
        from src.shared_services.sast_scanner import run_semgrep
        from src.shared_services.secret_scanner import run_gitleaks
        from src.shared_services.dependency_scanner import run_dependency_scanners
        
        # TRD: Run scanners in parallel, as Semgrep ignores .git 
        # and Gitleaks relies on it simultaneously. SCA acts independently on manifests.
        sast_result, secrets_result, _ = await asyncio.gather(
            run_semgrep(container, target_dir, job_id, db_client),
            run_gitleaks(container, target_dir, job_id, db_client),
            run_dependency_scanners(container, target_dir, job_id, db_client, detected)
        )
        
        if not sast_result or not secrets_result:
            return  # Exited cleanly due to crash/timeout explicitly handled by individual scanners DB hook
            
        print(f"Job {job_id} functionally scanned for SAST, Secrets, and Dependencies.")
        
        # TRD Explicit Instruction: secondary cleanup step (back in Feature 4 equivalent timing) 
        # explicitly deletes the .git directory before moving to Triage.
        await execute_in_container(container, f"rm -rf {target_dir}/.git")
        
        # Start Feature 9: AI-Powered Vulnerability Triage
        await sync_job_status(job_id, "triaging")
        from src.shared_services.ai_triage import run_ai_triage
        # Start Feature 10: AI-Powered Dependency Hallucination & Typosquat Detection
        from src.shared_services.dependency_hallucination import run_dependency_hallucination_check
        
        triage_results = await asyncio.gather(
            run_ai_triage(container, target_dir, job_id, db_client),
            run_dependency_hallucination_check(container, target_dir, job_id, db_client, detected)
        )
        triage_success = triage_results[0]
        if not triage_success:
            print(f"Job {job_id} triage skipped or failed API setup. Proceeding.")
            
        print(f"Job {job_id} triage complete.")
        
        # Start Feature 11: Report Compilation
        from src.shared_services.report_compiler import compile_report
        await compile_report(job_id, db_client)
        
        # Finish the job successfully
        await sync_job_status(job_id, "completed")
    finally:
        # Atomic decrement of backpressure tokens
        await redis.decr(active_redis_key)
        
        # TRD states Feature 12 (cleanup) kills container regardless of success or failure.
        # Once we wire the whole pipeline, this teardown hook belongs at the end of the *pipeline*, 
        # not the clone step. For MVP and test-safety right now, this shuts down the sandbox.
        if container:
            await teardown_container(container)
