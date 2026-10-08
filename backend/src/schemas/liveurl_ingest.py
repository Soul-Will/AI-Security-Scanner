from pydantic import BaseModel, HttpUrl, Field
from typing import Optional

class LiveUrlIngestRequest(BaseModel):
    url: HttpUrl = Field(..., description="The Live URL to scan")
    auth_acknowledged: bool = Field(
        ..., 
        description="Mandatory authorization acknowledgement flag. Must be true."
    )
    user_id: str = Field(..., description="User ID from Supabase auth")

class LiveUrlIngestResponse(BaseModel):
    status: str
    job_id: str
    message: str
    url: str
