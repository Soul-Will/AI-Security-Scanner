from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.routers import scans
from src.routers import github

from arq import create_pool

from src.shared_services.redis import redis_settings

app = FastAPI(title="AI Security Scanner")
app.include_router(github.router)
app.include_router(scans.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://192.168.1.19:3000",
        "http://localhost:3000",
        "http://127.0.0.1:3000"
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def health_check():
    return {"status": "ok", "message": "Backend is running!"}

@app.get("/api/scans/{scan_id}")
def get_scan(scan_id: str):
    return {"scan_id": scan_id, "status": "completed", "vulnerabilities": []}

@app.post("/test-task")
async def enqueue_test_task():
    redis = await create_pool(redis_settings)

    job = await redis.enqueue_job("test_task")

    await redis.close()

    return {
        "status": "queued",
        "job_id": job.job_id,
    }