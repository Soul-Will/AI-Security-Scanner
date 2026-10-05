import posixpath
import json
import asyncio
import re
import httpx
from datetime import datetime, timezone
from src.shared_services.docker_sandbox import execute_in_container
from src.shared_services.ai_triage import get_llm_client, parse_llm_json_response
from config import LLM_PROVIDER, LLM_MODEL_NAME

# Limit concurrent HTTP registry requests to avoid hammering npm/pypi
REGISTRY_SEMAPHORE = asyncio.Semaphore(10)

async def _check_npm_live(package_name: str) -> bool:
    """Check if an npm package legitimately exists on registry.npmjs.org"""
    url = f"https://registry.npmjs.org/{package_name}"
    async with REGISTRY_SEMAPHORE:
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                resp = await client.get(url)
                if resp.status_code == 200:
                    return True
                if resp.status_code == 404:
                    return False
            except Exception:
                pass 
    # Degrade gracefully if unavailable
    return None

async def _check_pypi_live(package_name: str) -> bool:
    """Check if a pip package legitimately exists on pypi.org"""
    url = f"https://pypi.org/pypi/{package_name}/json"
    async with REGISTRY_SEMAPHORE:
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                resp = await client.get(url)
                if resp.status_code == 200:
                    return True
                if resp.status_code == 404:
                    return False
            except Exception:
                pass
    # Degrade gracefully if unavailable
    return None

async def run_dependency_hallucination_check(container, target_dir, job_id, db_client, detected_stacks):
    """
    Feature 10: AI-Powered Dependency Hallucination & Typosquat Detection
    Takes the detected stacks, parses their dependencies, optionally checks live registries,
    and asks the LLM to triage for hallucination/typosquatting/deprecation.
    """
    if not detected_stacks:
        return

    started_at = datetime.now(timezone.utc).isoformat()
    findings_count = 0
    error_msg = None

    try:
        tasks = []
        for stack in detected_stacks:
            ecosystem = stack.get("ecosystem")
            manifest_path = stack.get("manifest_path")
            
            if ecosystem == "npm":
                tasks.append(_process_npm_manifest(container, target_dir, manifest_path, job_id, db_client))
            elif ecosystem == "pip":
                tasks.append(_process_pip_manifest(container, target_dir, manifest_path, job_id, db_client))
            # maven is explicitly excluded from MVP feature 8 and 10

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for res in results:
                if isinstance(res, int):
                    findings_count += res
                elif isinstance(res, Exception):
                    error_msg = str(res) # Store last error

    except Exception as e:
        error_msg = str(e)
    finally:
        completed_at = datetime.now(timezone.utc).isoformat()
        
        # Record the triage run for Feature 10
        triage_run_data = {
            "scan_job_id": job_id,
            "llm_provider": LLM_PROVIDER,
            "model_name": LLM_MODEL_NAME,
            "triage_run_type": "dependency_hallucination_check",
            "status": "failed" if error_msg else "completed",
            "findings_processed_count": findings_count,
            "error_message": error_msg,
            "started_at": started_at,
            "completed_at": completed_at
        }
        try:
            db_client.table("triage_runs").insert(triage_run_data).execute()
        except Exception as e:
            print(f"Failed to insert dependency_hallucination_check triage_run: {e}")


async def _process_npm_manifest(container, target_dir, manifest_path, job_id, db_client) -> int:
    """Parse package.json natively and process."""
    abs_manifest = posixpath.join(target_dir, manifest_path)
    exit_code, output = await execute_in_container(container, f"cat {abs_manifest}", timeout_seconds=10)
    if exit_code != 0:
        return 0

    try:
        parsed = json.loads(output.decode('utf-8'))
        deps = list(parsed.get('dependencies', {}).keys()) + list(parsed.get('devDependencies', {}).keys())
    except Exception:
        return 0
    
    # Clean uniquely
    deps = list(set(deps))
    if not deps:
        return 0

    return await _evaluate_dependencies(deps, "npm", manifest_path, job_id, db_client)

async def _process_pip_manifest(container, target_dir, manifest_path, job_id, db_client) -> int:
    """Parse requirements.txt securely."""
    abs_manifest = posixpath.join(target_dir, manifest_path)
    exit_code, output = await execute_in_container(container, f"cat {abs_manifest}", timeout_seconds=10)
    if exit_code != 0:
        return 0
    
    lines = output.decode('utf-8').splitlines()
    deps = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        # Extract basic package name before ==, >=, etc.
        match = re.match(r'^([a-zA-Z0-9_\-]+)', line)
        if match:
            deps.append(match.group(1))

    deps = list(set(deps))
    if not deps:
        return 0

    return await _evaluate_dependencies(deps, "pip", manifest_path, job_id, db_client)

async def _evaluate_dependencies(packages: list, ecosystem: str, manifest_path: str, job_id: str, db_client) -> int:
    """
    Perform optional live checking and then hand over to LLM.
    Batch size = 25 to avoid overwhelming the LLM prompt.
    """
    findings_saved = 0
    batch_size = 25
    
    # We will use the centralized LLM client from ai_triage
    client = get_llm_client()

    for i in range(0, len(packages), batch_size):
        batch = packages[i:i+batch_size]
        
        # 1. Do live registry checks concurrency
        check_tasks = []
        for pkg in batch:
            if ecosystem == "npm":
                check_tasks.append(_check_npm_live(pkg))
            else:
                check_tasks.append(_check_pypi_live(pkg))
                
        live_results = await asyncio.gather(*check_tasks)
        
        # Prepare context for LLM
        deps_context = []
        for pkg, is_live in zip(batch, live_results):
            live_status = "Unknown (network error/degraded)"
            if is_live is True:
                live_status = "Exists on registry"
            elif is_live is False:
                live_status = "DOES NOT EXIST on registry (STRONG hallucination/typosquat signal)"
            deps_context.append(f"- Name: {pkg} | Live Registry Status: {live_status}")
            
        deps_text = "\n".join(deps_context)
        
        prompt = f"""
You are an expert software security analyst. Review the following {ecosystem} dependencies.
Your task is to identify packages that are:
1. Hallucinated (fake AI-invented packages)
2. Typosquatted (malicious packages mimicking legitimate ones, e.g. 'reqeusts' instead of 'requests')
3. Deprecated (legitimate packages that are officially deprecated, e.g. 'request' in npm)
4. Legitimate (safe, valid, well-known)

Context:
{deps_text}

Output a strictly formatted JSON array of objects. Do not wrap in markdown tags like ```json.
Each object must have the following keys:
- "dependency_name": The exact string name of the package.
- "status": One of strictly ['suspicious_hallucinated', 'suspicious_typosquat', 'deprecated', 'legitimate']
- "rationale": Brief textual explanation of why. If legitimate, simply put "Standard legitimate package".
- "severity": If hallucinated or typosquat, MUST be "high". If deprecated, MUST be "low". If legitimate, "info".

Example format:
[
  {{"dependency_name": "express", "status": "legitimate", "rationale": "Standard web framework", "severity": "info"}},
  {{"dependency_name": "reqeusts", "status": "suspicious_typosquat", "rationale": "Common typosquat of requests", "severity": "high"}}
]
"""
        try:
            # LLM API Call with Backoff (re-use AI Triage semaphore if needed, though this scales per job)
            from src.shared_services.ai_triage import LLM_SEMAPHORE
            
            async with LLM_SEMAPHORE:
                if LLM_PROVIDER == "groq":
                    response = await client.chat.completions.create(
                        model=LLM_MODEL_NAME,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.1,
                        # max_tokens=1024
                    )
                    content = response.choices[0].message.content
                else: # Gemini
                    response = await client.aio.models.generate_content(
                        model=LLM_MODEL_NAME,
                        contents=prompt
                    )
                    content = response.text
                    
                parsed_json = parse_llm_json_response(content)
                if isinstance(parsed_json, list):
                    for item in parsed_json:
                        if item.get("status") in ["suspicious_hallucinated", "suspicious_typosquat", "deprecated"]:
                            # Emit risk finding
                            _insert_dependency_finding(
                                db_client, job_id, manifest_path, ecosystem, item
                            )
                            findings_saved += 1
                            
        except Exception as e:
            print(f"Error during LLM dependency triage batch: {e}")
            
    return findings_saved

def _insert_dependency_finding(db_client, job_id, manifest_path, ecosystem, item):
    """Insert into findings and finding_dependency_details"""
    try:
        # Schema definition mapping
        severity = item.get("severity", "info").lower()
        if severity not in ["high", "low", "info"]:
            severity = "info" # fallback
            
        finding_data = {
            "scan_job_id": job_id,
            "finding_type": "dependency_risk",
            "file_path": manifest_path,
            "severity": severity,
            "classification": "unverified", 
            "ai_specific_flag": True,
            "explanation": item.get("rationale", "No explanation provided")
        }
        
        res = db_client.table("findings").insert(finding_data).execute()
        if res.data:
            finding_id = res.data[0]['id']
            
            dep_data = {
                "finding_id": finding_id,
                "dependency_name": item.get("dependency_name", "unknown"),
                "ecosystem": ecosystem,
                "dependency_status": item.get("status")
            }
            db_client.table("finding_dependency_details").insert(dep_data).execute()
            
    except Exception as e:
        print(f"Failed to record hallucination finding: {e}")
