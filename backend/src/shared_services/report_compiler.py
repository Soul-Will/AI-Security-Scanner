import asyncio
import traceback
from supabase import Client

async def compile_report(job_id: str, db_client: Client) -> bool:
    """
    Summarizes the job into a structured denormalized aggregation record (reports).
    Tracks partial scan results from scanner_runs and triage_runs.
    """
    print(f"\n[{job_id}] Compiling final vulnerability report...")
    
    try:
        # 1. Fetch non-dismissed findings
        findings_resp = db_client.table("findings")\
            .select("severity, finding_type")\
            .eq("scan_job_id", job_id)\
            .eq("is_dismissed", False)\
            .execute()
            
        findings = findings_resp.data if findings_resp.data else []
        
        # 2. Count standard findings dynamically
        total_findings = len(findings)
        critical_count = sum(1 for f in findings if f.get("severity") == "critical")
        high_count = sum(1 for f in findings if f.get("severity") == "high")
        medium_count = sum(1 for f in findings if f.get("severity") == "medium")
        low_count = sum(1 for f in findings if f.get("severity") == "low")
        info_count = sum(1 for f in findings if f.get("severity") == "info")
        
        # 3. Tally separate metrics
        secrets_count = sum(1 for f in findings if f.get("finding_type") == "secret")
        dependency_issues_count = sum(1 for f in findings if f.get("finding_type") in ("dependency_vulnerability", "dependency_risk"))
        
        # 4. Check for scan/triage degradation
        is_partial = False
        partial_reasons = []
        
        # Check scanner_runs
        scanners_resp = db_client.table("scanner_runs")\
            .select("scanner_type, status, error_message")\
            .eq("scan_job_id", job_id)\
            .in_("status", ["failed", "partial"])\
            .execute()
            
        if scanners_resp.data:
            is_partial = True
            for run in scanners_resp.data:
                err = run.get('error_message') or 'Unknown error'
                partial_reasons.append(f"{run['scanner_type']} ({run['status']}): {err}")
                
        # Check triage_runs
        triage_resp = db_client.table("triage_runs")\
            .select("triage_run_type, status, error_message")\
            .eq("scan_job_id", job_id)\
            .eq("status", "failed")\
            .execute()
            
        if triage_resp.data:
            is_partial = True
            for run in triage_resp.data:
                err = run.get('error_message') or 'Unknown error'
                partial_reasons.append(f"{run['triage_run_type']} (failed): {err}")
                
        partial_reason_str = " | ".join(partial_reasons) if is_partial else None
        
        # 5. Persist compiled summary directly into the reports table
        report_payload = {
            "scan_job_id": job_id,
            "report_version": "1.0",
            "total_findings": total_findings,
            "critical_count": critical_count,
            "high_count": high_count,
            "medium_count": medium_count,
            "low_count": low_count,
            "info_count": info_count,
            "secrets_count": secrets_count,
            "dependency_issues_count": dependency_issues_count,
            "is_partial": is_partial,
            "partial_reason": partial_reason_str
        }
        
        db_client.table("reports").insert(report_payload).execute()
        
        print(f"[{job_id}] Report generated successfully. Total verified findings: {total_findings} (Partial: {is_partial})")
        return True
        
    except Exception as e:
        print(f"[{job_id}] Report compilation failed: {e}")
        traceback.print_exc()
        return False
