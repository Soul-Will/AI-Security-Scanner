import os
import json
import asyncio
from datetime import datetime, timezone
import docker
from typing import Dict, Any, List
from groq import AsyncGroq
from google import genai
from google.genai import types
from src.shared_services.docker_sandbox import execute_in_container
from src.shared_services.secret_scanner import redact_snippet
from config import LLM_PROVIDER, LLM_MODEL_NAME

# Shared concurrency limit for LLM API calls across jobs/features
LLM_SEMAPHORE = asyncio.Semaphore(5)

def get_llm_client() -> Any:
    """Returns the configured LLM client based on LLM_PROVIDER"""
    if LLM_PROVIDER == "gemini":
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY missing")
        return genai.Client(api_key=api_key)
    else:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY missing")
        return AsyncGroq(api_key=api_key)

def parse_llm_json_response(content: str) -> Any:
    """Sanitizes markdown wrappers and parses JSON"""
    content = content.strip()
    if content.startswith("```json"):
        content = content[7:]
    if content.endswith("```"):
        content = content[:-3]
    return json.loads(content.strip())

SYSTEM_INSTRUCTION = """You are an application security expert.
You must return only a valid JSON object matching this exact schema:
{
  "classification": "true_positive" | "false_positive",
  "explanation": "Plain-English explanation of why this is true or false.",
  "suggested_fix": "Corrected code block (if true_positive, else empty).",
  "severity_level": "critical" | "high" | "medium" | "low" | "info"
}
"""

SAST_PROMPT = """Review the following code vulnerability finding:
Rule: {rule_id}
File: {file_path}
Baseline Severity: {baseline_severity}

Snippet Context:
{snippet}

Based on the surrounding code, classify if this is a True Positive (a real, potentially exploitable vulnerability) or a False Positive. Explain your reasoning. 
Always output JSON. You may downgrade the severity if mitigated by context, but NEVER upgrade it above the Baseline Severity."""

SECRET_PROMPT = """Review the following secret found in the code.
Rule: {rule_id}
File: {file_path}
Baseline Severity: {baseline_severity}

Snippet Context:
{snippet}

Based on the variable name, surrounding code, and file path, classify if this is a True Positive (a real, potentially live credential) or a False Positive (a dummy value, test credential, or documentation placeholder). Explain your reasoning.
Always output JSON. You may downgrade the severity if mitigated by context (e.g., test files), but NEVER upgrade it above the Baseline Severity."""


async def _extract_semgrep_context(container, target_dir: str, file_path: str, start_line: int, rule_id: str) -> str:
    """Extract a 51-line snippets for Semgrep and pipe it through redact_snippet"""
    min_line = max(1, start_line - 25)
    max_line = start_line + 25
    grab_cmd = f"sed -n '{min_line},{max_line}p' {target_dir}/{file_path}"
    
    r_code, r_out = await execute_in_container(container, grab_cmd)
    if r_code != 0:
        return ""
        
    raw_lines = r_out.decode('utf-8', errors='ignore').splitlines()
    
    # We pass dummy exact coordinates for the secret replacement, as we only need the generic regex blanket mask
    clean_snippet = redact_snippet(raw_lines, min_line, start_line, start_line, 1, 1, rule_id)
    return clean_snippet

async def _call_groq_llm(client: AsyncGroq, prompt_text: str, semaphore: asyncio.Semaphore, model_name: str) -> Dict[str, Any]:
    """Call Groq API with concurrency limits and exponential backoff"""
    async with semaphore:
        for backoff in [0, 2, 4, 8]:
            if backoff > 0:
                await asyncio.sleep(backoff)
            try:
                # HTTP timeout using a task wrapper since Groq async uses httpx internally (often default 60s)
                # But we ensure it wraps in asyncio.wait_for
                response = await asyncio.wait_for(
                    client.chat.completions.create(
                        model=model_name,
                        messages=[
                            {"role": "system", "content": SYSTEM_INSTRUCTION},
                            {"role": "user", "content": prompt_text}
                        ],
                        response_format={"type": "json_object"},
                        temperature=0.0
                    ),
                    timeout=60.0 # Strict 60-second HTTP timeout per finding
                )
                
                content = response.choices[0].message.content
                return json.loads(content)
                
            except asyncio.TimeoutError:
                raise TimeoutError("LLM call timed out after 60s")
            except Exception as e:
                if "429" in str(e) or "rate limit" in str(e).lower():
                    continue
                else:
                    raise e
                    
        raise Exception("Exhausted retries due to rate limits or errors")

async def _call_gemini_llm(client: genai.Client, prompt_text: str, semaphore: asyncio.Semaphore, model_name: str) -> Dict[str, Any]:
    """Call Gemini API with concurrency limits and exponential backoff"""
    async with semaphore:
        for backoff in [0, 2, 4, 8]:
            if backoff > 0:
                await asyncio.sleep(backoff)
            try:
                response = await asyncio.wait_for(
                    client.aio.models.generate_content(
                        model=model_name,
                        contents=prompt_text,
                        config=types.GenerateContentConfig(
                            system_instruction=SYSTEM_INSTRUCTION,
                            response_mime_type="application/json",
                            temperature=0.0
                        )
                    ),
                    timeout=60.0 # Strict 60-second HTTP timeout per finding
                )
                
                content = response.text.strip()
                # Sanitize markdown JSON block
                if content.startswith("```json"):
                    content = content[7:]
                if content.endswith("```"):
                    content = content[:-3]
                return json.loads(content.strip())
                
            except asyncio.TimeoutError:
                raise TimeoutError("LLM call timed out after 60s")
            except Exception as e:
                # If 429 Rate Limit or Quota Exceeded, we let it retry
                if "429" in str(e) or "quota" in str(e).lower() or "rate" in str(e).lower():
                    continue
                else:
                    raise e
                    
        raise Exception("Exhausted retries due to rate limits or errors")

def clamp_severity(baseline: str, recommended: str, is_secret: bool) -> str:
    """Enforce severity ceilings. Never upgrade baseline."""
    levels = ["info", "low", "medium", "high", "critical"]
    try:
        base_idx = levels.index(baseline.lower())
    except ValueError:
        base_idx = 0
        
    try:
        rec_idx = levels.index(recommended.lower())
    except ValueError:
        rec_idx = 0
        
    # Ceiling enforcement: take the MIN of the two indexes
    final_idx = min(base_idx, rec_idx)
    return levels[final_idx]

async def triage_finding(
    client: Any,
    provider: str,
    model_name: str,
    finding: Dict[str, Any], 
    container, 
    target_dir: str, 
    semaphore: asyncio.Semaphore, 
    scanner_type: str,
    triage_run_id: str,
    db_client,
    job_id: str,
    run_id: str
):
    """Processes a single finding, extracting context if needed, calls LLM, and inserts to DB."""
    try:
        finding_type = "vulnerability"
        prompt_template = SAST_PROMPT
        
        rule_id = finding.get("rule", finding.get("check_id", "unknown"))
        file_path = finding.get("file", finding.get("path", ""))
        start_line = finding.get("line", finding.get("start", {}).get("line", 1))
        
        # Ensure path is relative
        if file_path.startswith(target_dir):
            file_path = file_path[len(target_dir):]
        if file_path.startswith("/"):
            file_path = file_path[1:]
        
        if scanner_type == "semgrep":
            baseline = finding.get("extra", {}).get("normalized_severity", "low")
            snippet = await _extract_semgrep_context(container, target_dir, file_path, start_line, rule_id)
            if not snippet:
                # Use raw string if context extraction fails
                snippet = finding.get("extra", {}).get("lines", "")
        else: # gitleaks
            finding_type = "secret"
            prompt_template = SECRET_PROMPT
            baseline = "critical" # TRD states secret ceiling is critical
            snippet = finding.get("snippet", "")
            
        prompt = prompt_template.format(
            rule_id=rule_id,
            file_path=file_path,
            baseline_severity=baseline,
            snippet=snippet
        )
        
        try:
            if provider == "gemini":
                llm_result = await _call_gemini_llm(client, prompt, semaphore, model_name)
            else:
                llm_result = await _call_groq_llm(client, prompt, semaphore, model_name)
        except Exception as groq_err:
            print(f"LLM call failed for {file_path}:{start_line} - Error: {str(groq_err)}")
            # Degrade gracefully to unverified
            llm_result = {
                "classification": "unverified",
                "explanation": "AI Triage failed or timed out. Needs manual review.",
                "severity_level": baseline
            }
            
        final_classification = llm_result.get("classification", "unverified")
        if final_classification not in ["true_positive", "false_positive"]:
            final_classification = "unverified"
            
        is_dismissed = (final_classification == "false_positive")
        final_severity = clamp_severity(baseline, llm_result.get("severity_level", baseline), finding_type == "secret")
        
        db_client.table("findings").insert({
            "scan_job_id": job_id,
            "scanner_run_id": run_id,
            "triage_run_id": triage_run_id,
            "finding_type": finding_type,
            "file_path": file_path,
            "line_start": start_line,
            "code_snippet": snippet[:10000],  # DB boundary guard
            "rule_id": rule_id,
            "severity": final_severity,
            "classification": final_classification,
            "explanation": llm_result.get("explanation"),
            "suggested_fix": llm_result.get("suggested_fix"),
            "is_dismissed": is_dismissed,
            "triage_status": "completed" if final_classification in ["true_positive", "false_positive"] else "skipped"
        }).execute()
        
    except Exception as e:
        print(f"Error processing finding {finding}: {e}")
        # Insert degraded version
        db_client.table("findings").insert({
            "scan_job_id": job_id,
            "scanner_run_id": run_id,
            "triage_run_id": triage_run_id,
            "finding_type": "vulnerability" if scanner_type == "semgrep" else "secret",
            "file_path": finding.get("path", ""),
            "severity": finding.get("extra", {}).get("normalized_severity", "critical"),
            "classification": "unverified",
            "explanation": f"Failed during triage processing: {e}",
            "is_dismissed": False,
            "triage_status": "failed"
        }).execute()

async def run_ai_triage(container: docker.models.containers.Container, target_dir: str, job_id: str, db_client) -> bool:
    """
    Kicks off AI Vulnerability triage on SAST and Secret findings using a shared llm client.
    """
    provider = LLM_PROVIDER
    model_name = LLM_MODEL_NAME
    
    try:
        client = get_llm_client()
    except ValueError as e:
        print(f"Skipping triage: {e}")
        return False
        
    runs_resp = db_client.table("scanner_runs").select("*").eq("scan_job_id", job_id).eq("status", "completed").execute()
    completed_runs = runs_resp.data if runs_resp.data else []
    
    # Filter only the types we triage for vulnerability (semgrep and gitleaks)
    target_runs = [r for r in completed_runs if r["scanner_type"] in ["semgrep", "gitleaks"]]
    
    if not target_runs:
        return True
        
    # Initialize triage run session
    t_run = db_client.table("triage_runs").insert({
        "scan_job_id": job_id,
        "llm_provider": provider,
        "model_name": model_name,
        "triage_run_type": "vulnerability_triage",
        "status": "running",
        "started_at": datetime.now(timezone.utc).isoformat()
    }).execute()
    
    if not t_run.data:
        return False
        
    triage_run_id = t_run.data[0]["id"]
    
    tasks = []
    
    for run in target_runs:
        run_id = run["id"]
        findings = run.get("raw_output", {}).get("findings", [])
        if run["scanner_type"] == "semgrep":
            # Extract list from Semgrep raw output format
            # Let's map how run_semgrep outputs it. It wraps inside "raw_output": {"findings": mapped_findings}
            pass
            
        for finding in findings:
            tasks.append(
                triage_finding(
                    client=client,
                    provider=provider,
                    model_name=model_name,
                    finding=finding,
                    container=container,
                    target_dir=target_dir,
                    semaphore=LLM_SEMAPHORE,
                    scanner_type=run["scanner_type"],
                    triage_run_id=triage_run_id,
                    db_client=db_client,
                    job_id=job_id,
                    run_id=run_id
                )
            )
            
    if tasks:
        await asyncio.gather(*tasks)
        
    db_client.table("triage_runs").update({
        "status": "completed",
        "findings_processed_count": len(tasks),
        "completed_at": datetime.now(timezone.utc).isoformat()
    }).eq("id", triage_run_id).execute()

    return True
