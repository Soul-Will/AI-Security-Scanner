from pydantic import BaseModel, HttpUrl, Field
from typing import Optional

class GithubIngestRequest(BaseModel):
    url: HttpUrl = Field(..., description="The GitHub repository URL")
    pat: Optional[str] = Field(
        None, 
        description="Optional Classic Personal Access Token with repo scope"
    )
    user_id: str = Field(..., description="User ID from Supabase auth")

class GithubIngestResponse(BaseModel):
    status: str
    job_id: str
    message: str
