import json
import re
import asyncio
from datetime import datetime, timezone
import docker
from typing import Dict, Any, List

from src.shared_services.ai_triage import get_llm_client, _call_groq_llm, _call_gemini_llm, clamp_severity, LLM_SEMAPHORE, SYSTEM_INSTRUCTION
from src.shared_services.liveurl_taxonomy import LIVE_URL_TAXONOMY, UNCATEGORIZED_TAXONOMY
from src.shared_services.docker_sandbox import execute_in_container
from config import LLM_PROVIDER, LLM_MODEL_NAME

def redact_text(text: str) -> str:
    """
    Applies regex masking mandated by TRD Feature 8 to raw text before LLM transmission.
    Checks Anthropic, OpenAI, Groq, AWS Bedrock.
    """
    if not text:
        return ""
        
    t = re.sub(r'(sk-[a-zA-Z0-9]{32,100})', lambda m: f"[REDACTED rule=openai-key len={len(m.group(1))} looks_placeholder=false]", text, flags=re.IGNORECASE)
    t = re.sub(r'(sk-ant-[a-zA-Z0-9\-_]{32,100})', lambda m: f"[REDACTED rule=anthropic-key len={len(m.group(1))} looks_placeholder=false]", t, flags=re.IGNORECASE)
    t = re.sub(r'(gsk_[a-zA-Z0-9]{32,90})', lambda m: f"[REDACTED rule=groq-key len={len(m.group(1))} looks_placeholder=false]", t, flags=re.IGNORECASE)
    # AWS Bedrock / SigV4 roughly matches AKIA
    t = re.sub(r'(AKIA[0-9A-Z]{16})', lambda m: f"[REDACTED rule=aws-key len={len(m.group(1))} looks_placeholder=false]", t, flags=re.IGNORECASE)
    
    return t


ZAP_PROMPT = """Review the following DAST vulnerability alert from OWASP ZAP:
Alert Name: {alert_name}
Risk Parameter: {param}
Evidence: {evidence}
Baseline Severity: {baseline_severity}
Description: {description}

Based on this, classify if this is a True Positive (a real vulnerability) or a False Positive.
Also, classify the finding exclusively using one of the following exact 'code' mappings:
- dom_xss
- exposed_secrets_js
- broken_access_control
- security_misconfig
- info_leakage
- uncategorized_other

Flag 'is_ai_flaw' to true if it indicates an AI-generated specific risk (e.g., exposed AI provider payload or injection).
Always output JSON matching this exact schema:
{{
  "classification": "true_positive" | "false_positive",
  "taxonomy_category_code": "...",
  "explanation": "Plain-English explanation...",
  "suggested_fix": "Remediation guidance...",
  "severity_level": "critical" | "high" | "medium" | "low" | "info",
  "is_ai_flaw": boolean
}}
You may downgrade severity if contextually mitigated, but NEVER upgrade it completely above the Baseline Severity.
"""


JS_BUNDLE_PROMPT = """Review the following frontend JavaScript bundle extracted from a live application crawl.
Chunk size: ~60k tokens.

Look for exposed secrets (API keys, credentials), AI-specific risks, and insecure frontend logic/access control gaps.
Identify vulnerabilities mapping ONLY to these 'code' categories:
- dom_xss
- exposed_secrets_js
- broken_access_control
- security_misconfig
- info_leakage

Always output JSON matching this exact schema:
{{
  "findings": [
    {{
      "classification": "true_positive",
      "taxonomy_category_code": "...",
      "explanation": "Why this is insecure...",
      "suggested_fix": "Fix...",
      "severity_level": "critical" | "high" | "medium" | "low" | "info",
      "is_ai_flaw": boolean,
      "snipped_evidence": "The small code piece causing this (max 200 chars)"
    }}
  ]
}}
If no findings, return an empty list for 'findings'.
"""

def map_zap_risk_to_severity(risk_id: str) -> str:
    mapping = {"0": "info", "1": "low", "2": "medium", "3": "high"}
    return mapping.get(str(risk_id), "medium")

async def triage_zap_alert(
    client, provider, model_name, alert: Dict[str, Any], semaphore, triage_run_id, db_client, job_id, run_id
):
    try:
        baseline = map_zap_risk_to_severity(alert.get("riskcode", "2"))
        
        # Redact any evidence snippets before throwing to Groq
        safe_evidence = redact_text(alert.get("evidence", ""))
        safe_desc = redact_text(alert.get("desc", ""))
        
        prompt = ZAP_PROMPT.format(
            alert_name=alert.get("alert", "Unknown Alert"),
            param=alert.get("param", ""),
            evidence=safe_evidence[:2000],
            baseline_severity=baseline,
            description=safe_desc[:1000]
        )
        
        # Dispatch to Groq primarily for discrete ZAP findings
        if provider == "gemini":
            res = await _call_gemini_llm(client, prompt, semaphore, model_name)
        else:
            res = await _call_groq_llm(client, prompt, semaphore, model_name)

        final_cat = res.get("taxonomy_category_code", "uncategorized_other")
        if final_cat not in LIVE_URL_TAXONOMY:
            final_cat = "uncategorized_other"

        final_severity = clamp_severity(baseline, res.get("severity_level", baseline), False)
        classification = res.get("classification", "unverified")
        
        is_dismissed = (classification == "false_positive")
        triage_status = "completed" if classification in ["true_positive", "false_positive"] else "unverified"
        
        instances = alert.get("instances", [])
        alert_url = alert.get("url", "")
        if not alert_url and instances and isinstance(instances, list) and len(instances) > 0:
            alert_url = instances[0].get("uri", "")
        
        f_insert = db_client.table("findings").insert({
            "scan_job_id": job_id,
            "scanner_run_id": run_id,
            "triage_run_id": triage_run_id,
            "finding_type": "vulnerability",
            "file_path": alert_url[:255],
            "line_start": 1,
            "code_snippet": safe_evidence[:10000],
            "rule_id": alert.get("pluginId", "zap-alert"),
            "severity": final_severity,
            "classification": classification,
            "explanation": res.get("explanation"),
            "suggested_fix": res.get("suggested_fix"),
            "is_dismissed": is_dismissed,
            "triage_status": triage_status,
            "ai_specific_flag": bool(res.get("is_ai_flaw", False))
        }).execute()
        
        if f_insert.data:
            f_id = f_insert.data[0]["id"]
            cat_resp = db_client.table("finding_categories").select("id").eq("code", final_cat).execute()
            if cat_resp.data:
                db_client.table("finding_category_map").insert({"finding_id": f_id, "category_id": cat_resp.data[0]["id"]}).execute()
                
    except Exception as e:
        print(f"Error triaging ZAP alert: {e}")
        # Insert degraded version
        db_client.table("findings").insert({
            "scan_job_id": job_id,
            "scanner_run_id": run_id,
            "triage_run_id": triage_run_id,
            "finding_type": "vulnerability",
            "file_path": alert.get("url", ""),
            "severity": map_zap_risk_to_severity(alert.get("riskcode", "2")),
            "classification": "unverified",
            "explanation": f"Failed during AI triage processing: {e}",
            "is_dismissed": False,
            "triage_status": "failed"
        }).execute()


async def triage_js_bundle_chunk(client, provider, model_name, chunk: str, semaphore, triage_run_id, db_client, job_id, run_id):
    try:
        prompt = JS_BUNDLE_PROMPT + f"\n\nJS Fragment:\n{chunk}"
        if provider == "gemini":
            res = await _call_gemini_llm(client, prompt, semaphore, model_name)
        else:
            res = await _call_groq_llm(client, prompt, semaphore, model_name)
        
        findings = res.get("findings", [])
        for f in findings:
            baseline = f.get("severity_level", "medium") # No scanner baseline for raw JS snippets, use derived
            
            final_cat = f.get("taxonomy_category_code", "uncategorized_other")
            if final_cat not in LIVE_URL_TAXONOMY:
                final_cat = "uncategorized_other"
                
            f_insert = db_client.table("findings").insert({
                "scan_job_id": job_id,
                "scanner_run_id": run_id,
                "triage_run_id": triage_run_id,
                "finding_type": "vulnerability",
                "file_path": "frontend_assets/bundle.js",
                "line_start": 1,
                "code_snippet": redact_text(f.get("snipped_evidence", ""))[:10000], 
                "rule_id": "js_bundle_analysis",
                "severity": baseline,
                "classification": f.get("classification", "unverified"),
                "explanation": f.get("explanation"),
                "suggested_fix": f.get("suggested_fix"),
                "is_dismissed": False,
                "triage_status": "completed",
                "ai_specific_flag": bool(f.get("is_ai_flaw", False))
            }).execute()
            
            if f_insert.data:
                f_id = f_insert.data[0]["id"]
                cat_resp = db_client.table("finding_categories").select("id").eq("code", final_cat).execute()
                if cat_resp.data:
                    db_client.table("finding_category_map").insert({"finding_id": f_id, "category_id": cat_resp.data[0]["id"]}).execute()
                    
            
    except Exception as e:
        print(f"Error triaging JS bundle chunk: {e}")


async def run_liveurl_triage(container: docker.models.containers.Container, target_dir: str, job_id: str, db_client) -> bool:
    """
    Executes Feature 8 rules parsing ZAP JSON results and chunking JS bundles to AI providers.
    """
    try:
        # TRD allows splitting providers - Groq for rapid ZAP, Gemini for chunking JS
        client = get_llm_client() 
    except ValueError as e:
        print(f"Skipping triage: {e}")
        return False
        
    t_run = db_client.table("triage_runs").insert({
        "scan_job_id": job_id,
        "llm_provider": LLM_PROVIDER,
        "model_name": LLM_MODEL_NAME,
        "triage_run_type": "vulnerability_triage",
        "status": "running",
        "started_at": datetime.now(timezone.utc).isoformat()
    }).execute()
    
    if not t_run.data:
        return False
        
    triage_run_id = t_run.data[0]["id"]
    
    # 1. Fetch ZAP JSON findings
    runs_resp = db_client.table("scanner_runs").select("*").eq("scan_job_id", job_id).eq("status", "completed").eq("scanner_type", "owasp_zap").execute()
    zap_runs = runs_resp.data if runs_resp.data else []
    
    tasks = []
    
    if zap_runs:
        run = zap_runs[0]
        run_id = run["id"]
        raw_output = run.get("raw_output", {})
        # ZAP puts alerts in site[0]['alerts'] usually
        sites = raw_output.get("site", [])
        for site in sites:
            alerts = site.get("alerts", [])
            for alert in alerts:
                tasks.append(
                    triage_zap_alert(client, LLM_PROVIDER, LLM_MODEL_NAME, alert, LLM_SEMAPHORE, triage_run_id, db_client, job_id, run_id)
                )

    # 2. Process JS Bundle
    code, js_bytes = await execute_in_container(container, f"cat {target_dir}/assets_js.txt")
    if code == 0 and js_bytes.strip():
        js_text = js_bytes.decode('utf-8', errors='ignore')
        
        # Redact raw secrets globally beforehand
        safe_js = redact_text(js_text)
        
        # Chunking: ~60k tokens roughly = 240,000 chars. We will split by 200,000 chars for safety.
        CHUNK_SIZE = 200000 
        chunks = [safe_js[i:i+CHUNK_SIZE] for i in range(0, len(safe_js), CHUNK_SIZE)]
        
        # If no ZAP runs exist, we still want to map JS findings to the primary run ID?
        # A mock run ID or just grab any
        run_id_for_js = zap_runs[0]["id"] if zap_runs else None
        
        # Push chunk tasks specifically relying on GEMINI models when applicable
        # (Assuming the system will route natively but passing through normal client block)
        for chunk in chunks:
            tasks.append(
                triage_js_bundle_chunk(client, LLM_PROVIDER, LLM_MODEL_NAME, chunk, LLM_SEMAPHORE, triage_run_id, db_client, job_id, run_id_for_js)
            )

    if tasks:
        await asyncio.gather(*tasks)
        
    db_client.table("triage_runs").update({
        "status": "completed",
        "findings_processed_count": len(tasks),
        "completed_at": datetime.now(timezone.utc).isoformat()
    }).eq("id", triage_run_id).execute()
    
    return True
