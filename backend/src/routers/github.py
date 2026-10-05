from fastapi import APIRouter, HTTPException, Depends
from arq import create_pool
from uuid import uuid4
from src.schemas.github_ingest import GithubIngestRequest, GithubIngestResponse
from src.shared_services.github_api import validate_github_url_and_metadata
from src.shared_services.db import get_supabase_client
from src.shared_services.redis import redis_settings

router = APIRouter(
    prefix="/api/v1/scan",
    tags=["GitHub Ingestion"]
)

@router.post("/github", response_model=GithubIngestResponse)
async def ingest_github_repo(request: GithubIngestRequest):
    # Rule 2.2 / TRD-01 Feature 1: Validate URL synchronously before any job row is created.
    # We pass the optional PAT down for scope validation.
    
    validation_result = await validate_github_url_and_metadata(str(request.url), request.pat)
    
    # If the function above returns, all edge validation has passed. 
    # Create the job identifier and the job record in Supabase.
    job_id = str(uuid4())
    supabase = get_supabase_client()
    
    # Insert row according to TRD-01 Rule R
    try:
        # 1. Insert root job row
        response = supabase.table("scan_jobs").insert({
            "id": job_id,
            "user_id": request.user_id,
            "input_channel": "github",
            "status": "queued"
        }).execute()
        
        # 2. Insert channel-specific detail row (Rule 4.1 Requirement #5)
        supabase.table("github_job_details").insert({
            "scan_job_id": job_id,
            "repo_url": validation_result["normalized_url"],
            "repo_owner": validation_result["owner"],
            "repo_name": validation_result["repo"],
            "visibility": validation_result["visibility"],
            "pat_provided": bool(request.pat),
            "pat_validation_status": "valid" if request.pat else "not_applicable"
        }).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database insertion failed: {e}")
    
    # Enqueue job to ARQ (FIFO backpressure handling, TRD-01 Feature 3 limits enforced in worker config)
    redis_pool = await create_pool(redis_settings)
    
    # TRD-01 Feature 2: Queue the PAT with a hard 5-minute TTL specifically for this job (plaintext in redis)
    if request.pat:
        await redis_pool.set(f"job_pat:{job_id}", request.pat, ex=300) # 300s = 5mins TTL
        
    try:
        # Route to Feature 3 (Secure Cloning Sandbox) - passing context
        await redis_pool.enqueue_job(
            "start_github_clone_sandbox", 
            job_id=job_id,
            user_id=request.user_id,
            repo_url=validation_result["normalized_url"],
            owner=validation_result["owner"],
            repo=validation_result["repo"],
            visibility=validation_result["visibility"],
            pat_supplied=bool(request.pat)
        )
    finally:
        await redis_pool.close()
    
    return GithubIngestResponse(
        status="queued",
        job_id=job_id,
        message="Scan queued for validation and processing."
    )
