from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.routers import scans

app = FastAPI(title="AI Security Scanner")
app.include_router(scans.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://192.168.1.19:3000"],  # Next.js default
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def health_check():
    return {"status": "ok", "message": "Backend is running!"}

@app.get("/api/scans/{scan_id}")
def get_scan(scan_id: str):
    return {"scan_id": scan_id, "status": "completed", "vulnerabilities": []}