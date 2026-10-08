from fastapi import APIRouter, HTTPException
from arq import create_pool
from uuid import uuid4
from src.schemas.liveurl_ingest import LiveUrlIngestRequest, LiveUrlIngestResponse
from src.shared_services.db import get_supabase_client
from src.shared_services.redis import redis_settings

router = APIRouter(
    prefix="/api/v1/scan",
    tags=["Live URL Ingestion"]
)

@router.post("/liveurl", response_model=LiveUrlIngestResponse)
async def ingest_live_url(request: LiveUrlIngestRequest):
    # Rule R / TRD-02 Feature 1: Validate authorization acknowledgement synchronously
    if not request.auth_acknowledged:
        raise HTTPException(
            status_code=400, 
            detail="Authorization acknowledgement is mandatory."
        )
    
    # Normalize URL cleanly (Pydantic already verified it's a valid HttpUrl format)
    normalized_url = str(request.url)
    
    # Check duplicate active scan job
    supabase = get_supabase_client()
    try:
        url_matches = supabase.table("url_job_details").select("scan_job_id").eq("target_url", normalized_url).execute()
        
        if url_matches.data:
            matched_ids = [m['scan_job_id'] for m in url_matches.data]
            active_statuses = ['queued', 'validating', 'preparing', 'crawling', 'scanning', 'triaging']
            
            status_check = supabase.table("scan_jobs").select("id, status").in_("id", matched_ids).execute()
            for job in status_check.data:
                if job['status'] in active_statuses:
                    raise HTTPException(
                        status_code=409, 
                        detail="Scan already in progress for this URL"
                    )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to check duplicate scans: {e}")

    job_id = str(uuid4())
    
    try:
        # 1. Insert root job row
        supabase.table("scan_jobs").insert({
            "id": job_id,
            "user_id": request.user_id,
            "input_channel": "url",
            "status": "queued"
        }).execute()
        
        # 2. Insert channel-specific detail row
        supabase.table("url_job_details").insert({
            "scan_job_id": job_id,
            "target_url": normalized_url,
            "ssrf_check_passed": False
        }).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database insertion failed: {e}")
        
    # Enqueue job to ARQ Worker
    redis_pool = await create_pool(redis_settings)
    try:
        await redis_pool.enqueue_job(
            "start_liveurl_scan",
            job_id=job_id,
            user_id=request.user_id,
            target_url=normalized_url
        )
    finally:
        await redis_pool.close()
        
    return LiveUrlIngestResponse(
        status="queued",
        job_id=job_id,
        message="Live URL scan queued for validation and processing.",
        url=normalized_url
    )
