from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from supabase import create_client

from config import SUPABASE_KEY, SUPABASE_URL
from src.utils.github import clone_and_scan_github

router = APIRouter()
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

class ScanRequest(BaseModel):
    input_type: str  # "github", "url", "zip", "docker"
    input_value: str

@router.post("/api/scans")
async def start_scan(request: ScanRequest):
    # Basic validation
    if request.input_type == "github" and "github.com" not in request.input_value:
        raise HTTPException(400, "Invalid GitHub URL")

    # Create scan record
    result = supabase.table("scans").insert({
        "input_type": request.input_type,
        "input_value": request.input_value,
        "status": "pending",
    }).execute()

    if not result.data:
        raise HTTPException(500, "Failed to create scan")

    scan_id = result.data[0]["id"]

    # Run the scanner
    if request.input_type == "github":
        scan_result = clone_and_scan_github(
            request.input_value,
            scan_id
        )

        # Update database
        supabase.table("scans").update({
            "status": scan_result["status"]
        }).eq("id", scan_id).execute()

        return {
            "scan_id": scan_id,
            **scan_result
        }

    raise HTTPException(400, "Unsupported input type")

