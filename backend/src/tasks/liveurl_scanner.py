import json
from src.shared_services.db import get_supabase_client
from src.utils.ssrf import validate_url_safety
from src.shared_services.docker_sandbox import provision_container, get_docker_client, teardown_container, execute_in_container
from src.shared_services.liveurl_crawler_payload import CRAWLER_SCRIPT_TEMPLATE
from src.shared_services.zap_scanner import run_zap_dast
from src.shared_services.liveurl_triage import run_liveurl_triage
from src.shared_services.report_compiler import compile_report

async def start_liveurl_scan(ctx, job_id: str, user_id: str, target_url: str):
    """
    ARQ Worker task for Live URL.
    Implements TRD-02 Feature 2 & 3 (Validation & SSRF Protection Engine / Reachability Gate).
    """
    supabase = get_supabase_client()
    
    print(f"[LiveURL Job {job_id}] Dequeued. Validating target: {target_url}")
    
    # 1. Update job to validating state early
    try:
        supabase.table("scan_jobs").update({"status": "validating"}).eq("id", job_id).execute()
    except Exception as e:
        print(f"[LiveURL Job {job_id}] DB Error updating to validating: {e}")
        return

    # 2. Extract domain and run SSRF check
    # TRD-02 Feature 2 specifies SSRF validation logic before proceeding to create ephemeral containers.
    is_safe, reason, resolved_ips = validate_url_safety(target_url)
    
    primary_ip = resolved_ips[0] if resolved_ips else "0.0.0.0"
    
    if not is_safe:
        print(f"[LiveURL Job {job_id}] Validation Failed. Blocked for: {reason}")
        # TRD Rulebook Section 6, Decision #9 & #1 — failure before compute -> rejected
        try:
            supabase.table("scan_jobs").update({
                "status": "rejected",
                "failure_code": "ssrf_blocked",
                "failure_reason": reason
            }).eq("id", job_id).execute()
            
            supabase.table("url_job_details").update({
                "ssrf_check_passed": False,
                "ssrf_rejection_reason": reason,
                "resolved_ip": primary_ip
            }).eq("scan_job_id", job_id).execute()
        except Exception as e:
            print(f"[LiveURL Job {job_id}] DB Error finalizing rejection state: {e}")
            
        return

    # 3. Target is safe. Pass the reachability gate.
    print(f"[LiveURL Job {job_id}] SSRF Check Passed. Target reachable.")
    try:
        supabase.table("url_job_details").update({
            "ssrf_check_passed": True,
            "resolved_ip": primary_ip
        }).eq("scan_job_id", job_id).execute()
        
        # advance to preparing
        supabase.table("scan_jobs").update({"status": "preparing"}).eq("id", job_id).execute()
    except Exception as e:
        print(f"[LiveURL Job {job_id}] DB Error on success transition: {e}")
        return
        
    # Feature 4: Provision Container
    container = None
    try:
        container = await provision_container(job_id)
    except Exception as e:
        supabase.table("scan_jobs").update({
            "status": "failed",
            "failure_code": "internal_error",
            "failure_reason": f"Sandbox provisioning failed: {str(e)}"
        }).eq("id", job_id).execute()
        return

    try:
        supabase.table("scan_jobs").update({"status": "crawling"}).eq("id", job_id).execute()
        print(f"[LiveURL Job {job_id}] Provisioned container. Entering crawl phase.")
        
        target_dir = f"/tmp/scan-job-{job_id}"
        
        # Inject script safely
        inject_cmd = "cat << 'EOF' > /tmp/crawler.py\n" + CRAWLER_SCRIPT_TEMPLATE + "\nEOF\n"
        exit_code, _ = await execute_in_container(container, inject_cmd, timeout_seconds=10)
        
        if exit_code != 0:
            raise Exception("Failed to inject crawler script into container.")
            
        print(f"[LiveURL Job {job_id}] Running crawler script...")
        # 10 minutes timeout (600s) as per standard robust crawl windows
        exit_code, output = await execute_in_container(container, f"python3 /tmp/crawler.py {target_url} {target_dir}", timeout_seconds=600)
        
        if exit_code != 0:
            supabase.table("scan_jobs").update({
                "status": "failed",
                "failure_code": "internal_error",
                "failure_reason": f"Crawler execution err code: {exit_code}"
            }).eq("id", job_id).execute()
            return
            
        # Parse metrics generated
        exit_code, out_bytes = await execute_in_container(container, f"cat {target_dir}/summary.json")
        if exit_code == 0:
            try:
                summary = json.loads(out_bytes.decode('utf-8'))
                supabase.table("url_job_details").update({
                    "crawl_pages_discovered": summary.get("crawl_pages_discovered", 0),
                    "crawl_forms_discovered": summary.get("crawl_forms_discovered", 0),
                    "crawl_api_endpoints_discovered": summary.get("crawl_api_endpoints_discovered", 0)
                }).eq("scan_job_id", job_id).execute()
                print(f"[LiveURL Job {job_id}] Crawl successfully returned metrics.")
            except Exception as e:
                print(f"[LiveURL Job {job_id}] JSON Parse error of summary: {e}")
                
        # Phase 5 & 6 transition marker
        supabase.table("scan_jobs").update({"status": "scanning"}).eq("id", job_id).execute()
        
        # Feature 6: Register Assets (Crawler already built HTML/JS/CSS blobs securely bounded to 20MB in the sandbox)
        supabase.table("url_job_details").update({
            "assets_storage_path": target_dir
        }).eq("scan_job_id", job_id).execute()
        
        print(f"[LiveURL Job {job_id}] Entering ZAP DAST engine (Feature 5)...")
        # Feature 5: Run ZAP DAST Scan
        await run_zap_dast(container, target_dir, job_id, supabase, target_url)
        
        # Feature 8: Triaging Phase
        print(f"[LiveURL Job {job_id}] Commencing Feature 8 AI Triage...")
        await run_liveurl_triage(container, target_dir, job_id, supabase)
        print(f"[LiveURL Job {job_id}] AI Triage process finished.")
        
        # Feature 9: Report Generation
        print(f"[LiveURL Job {job_id}] Assuring final report compilation...")
        await compile_report(job_id, supabase)
        
        supabase.table("scan_jobs").update({"status": "completed"}).eq("id", job_id).execute()
        print(f"[LiveURL Job {job_id}] Flow completely finished. Marked as completed.")
        
        
    except TimeoutError:
        print(f"[LiveURL Job {job_id}] Time Limit Exceeded (DAST/Crawler).")
        supabase.table("scan_jobs").update({
            "status": "failed",
            "failure_code": "timeout_exceeded"
        }).eq("id", job_id).execute()
    except Exception as e:
        print(f"[LiveURL Job {job_id}] Internal Failure: {e}")
        supabase.table("scan_jobs").update({
            "status": "failed",
            "failure_code": "internal_error",
            "failure_reason": str(e)
        }).eq("id", job_id).execute()
    finally:
        # TRD states Feature 12 (cleanup) kills container regardless of success or failure.
        if container:
            print(f"[LiveURL Job {job_id}] Tearing down temporary scanning container.")
            await teardown_container(container)
