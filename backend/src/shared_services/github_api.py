import httpx
from urllib.parse import urlparse
from fastapi import HTTPException
from src.config.github import GITHUB_LOOKUP_TIMEOUT_SECONDS, PERMITTED_GHE_HOSTS, GITHUB_METADATA_TOKEN

def extract_owner_repo(host: str, path: str) -> tuple[str, str]:
    parts = path.strip("/").split("/")
    if len(parts) >= 2:
        return parts[0], parts[1].replace(".git", "")
    return "", ""

async def validate_github_url_and_metadata(url_str: str, pat: str | None = None) -> dict:
    parsed = urlparse(url_str)
    host = parsed.hostname or ""
    
    # 1. Structural validation (Rule R - synchronous, 4xx, no job row)
    if host != "github.com" and host not in PERMITTED_GHE_HOSTS:
        raise HTTPException(
            status_code=400,
            detail="Invalid repository host. Must be github.com or a permitted GitHub Enterprise host."
        )
    
    owner, repo = extract_owner_repo(host, parsed.path)
    if not owner or not repo:
        raise HTTPException(
            status_code=400,
            detail="Malformed repository URL. Must include owner and repo."
        )

    # 2. Metadata lookup call against GitHub API
    # Bound by a strict 10-second timeout (TRD-01 Feature 1, §2.6)
    api_base_url = "https://api.github.com" if host == "github.com" else f"https://{host}/api/v3"
    api_url = f"{api_base_url}/repos/{owner}/{repo}"

    headers = {"Accept": "application/vnd.github.v3+json"}
    
    if pat:
        headers["Authorization"] = f"Bearer {pat}"
    elif GITHUB_METADATA_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_METADATA_TOKEN}"

    try:
        async with httpx.AsyncClient(timeout=GITHUB_LOOKUP_TIMEOUT_SECONDS) as client:
            response = await client.get(api_url, headers=headers)
            
            # TRD-01 Feature 1: No PAT supplied, 404 is ambiguous.
            if response.status_code == 404 and not pat:
                raise HTTPException(
                    status_code=404,
                    detail="Repository not found, or private. If private, add a Classic PAT with repo scope and resubmit."
                )

            # 403 or 429 rate-limit response -> fail-fast, no retries
            if response.status_code in (403, 429):
                raise HTTPException(
                    status_code=response.status_code,
                    detail="GitHub API rate limit exceeded or access forbidden."
                )
            
            # General error fallback
            if response.status_code >= 400:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"GitHub API Error: {response.text}"
                )
            
            repo_data = response.json()
            is_private = repo_data.get("private", False)
            
            # TRD-01 Feature 2: If PAT is supplied, validate token scope for 'repo'
            if pat:
                scopes = response.headers.get("x-oauth-scopes", "")
                if "repo" not in [s.strip() for s in scopes.split(",")]:
                    raise HTTPException(
                        status_code=400,
                        detail="Provided PAT is missing the required 'repo' scope."
                    )
            
            normalized_url = f"https://{host}/{owner}/{repo}"
            
            return {
                "normalized_url": normalized_url,
                "owner": owner,
                "repo": repo,
                "visibility": "private" if is_private else "public",
                "validation_status": "valid"
            }

    except httpx.TimeoutException:
        # TRD-01 Feature 1: timeout (>10s) -> immediate error, no retries, no row
        raise HTTPException(
            status_code=504,
            detail="GitHub metadata lookup timed out."
        )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to connect to GitHub API: {exc}"
        )
