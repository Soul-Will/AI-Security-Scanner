"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { supabase } from "@/lib/supabase";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ArrowLeft, RefreshCw, Search, CheckCircle2, Loader2, Sparkles, FileCode, AlertTriangle, Bug, Clock, ShieldCheck, Download } from "lucide-react";

const PIPELINE_STAGES = ["queued", "validating", "preparing", "scanning", "triaging", "completed"];

function PipelineStatusBar({ currentStatus }: { currentStatus: string }) {
  const isFailed = currentStatus === "failed" || currentStatus === "rejected";
  
  // Find current index
  let currentIndex = PIPELINE_STAGES.indexOf(currentStatus.toLowerCase());
  if (currentIndex === -1) {
    if (currentStatus === "cloning" || currentStatus === "extracting" || currentStatus === "crawling") currentIndex = 2; // Maps to "preparing" or "scanning" roughly
    else if (currentStatus === "triaging") currentIndex = 4;
    else if (currentStatus === "scanning") currentIndex = 3;
    else currentIndex = 0; 
  }

  return (
    <div className="w-full flex items-center justify-between gap-1.5 mt-8 mb-2">
      {PIPELINE_STAGES.map((stage, i) => {
        const isPassed = i <= currentIndex;
        const isCurrent = i === currentIndex;
        
        let barColor = "bg-slate-200";
        if (isPassed && !isFailed) barColor = "bg-emerald-600";
        if (isFailed && isPassed) barColor = "bg-rose-500";
        
        let textColor = "text-slate-500/80 font-medium";
        if (isCurrent && !isFailed) textColor = "text-slate-900 font-bold";
        else if (isPassed && !isFailed) textColor = "text-slate-700 font-medium";
        
        return (
          <div key={stage} className="flex-1 flex flex-col gap-2.5">
            <div className={`h-1 w-full rounded-full transition-colors duration-300 ${barColor}`} />
            <span className={`text-xs capitalize tracking-wide ${textColor}`}>
              {stage}
            </span>
          </div>
        );
      })}
    </div>
  );
}

export default function ScanDetailsPage() {
  const { id } = useParams() as { id: string };
  const router = useRouter();

  const [job, setJob] = useState<any>(null);
  const [report, setReport] = useState<any>(null);
  const [findings, setFindings] = useState<any[]>([]);
  const [jobDetails, setJobDetails] = useState<{title: string, subtitle: string}>({ title: "Analysis Target", subtitle: "Computing..." });
  const [loading, setLoading] = useState(true);

  // Filters
  const [filterClassification, setFilterClassification] = useState("all");
  const [filterSeverity, setFilterSeverity] = useState("all");

  const fetchScanData = async () => {
    try {
      // Fetch Job with relations
      const { data: jobData, error: jobError } = await supabase
        .from("scan_jobs")
        .select(`
          *,
          github_job_details(*),
          reports(*)
        `)
        .eq("id", id)
        .single();

      if (jobError) throw jobError;
      setJob(jobData);
      
      // Compute title / subtitle
      let t = jobData.id.split('-')[0];
      let s = "No URL provided";
      
      if (jobData.input_channel === "github" && jobData.github_job_details) {
         const gh = Array.isArray(jobData.github_job_details) ? jobData.github_job_details[0] : jobData.github_job_details;
         if (gh) {
           t = `${gh.repo_owner}/${gh.repo_name}`;
           s = gh.repo_url;
         }
      } else if (jobData.input_url) {
         t = jobData.input_url;
         s = jobData.input_url;
      }
      setJobDetails({ title: t, subtitle: s });

      // Handle Reports
      if (jobData.reports) {
        const r = Array.isArray(jobData.reports) ? jobData.reports[0] : jobData.reports;
        if (r) setReport(r);
      }

      // Fetch Findings
      const { data: findingsData } = await supabase
        .from("findings")
        .select("*")
        .eq("scan_job_id", id)
        .order("severity", { ascending: true }); 

      if (findingsData) {
        // Sort manually
        const sevs: Record<string, number> = { critical: 4, high: 3, medium: 2, low: 1, info: 0 };
        const sorted = findingsData.sort((a, b) => (sevs[b.severity?.toLowerCase()] || 0) - (sevs[a.severity?.toLowerCase()] || 0));
        setFindings(sorted);
      }

      // Check loop condition
      if (["completed", "failed", "rejected"].includes(jobData.status)) {
        return true; // done
      }
      return false; // keep polling
    } catch (err: any) {
      console.error(err);
      return true; // done on error
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!id) return;
    let intervalId: NodeJS.Timeout;
    
    fetchScanData().then((isDone) => {
      if (!isDone) {
        intervalId = setInterval(async () => {
          const done = await fetchScanData();
          if (done) clearInterval(intervalId);
        }, 5000);
      }
    });

    return () => clearInterval(intervalId);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  if (loading && !job) {
    return (
      <div className="flex w-full h-screen items-center justify-center">
        <div className="flex flex-col items-center gap-4 text-muted-foreground">
          <Loader2 className="w-12 h-12 animate-spin text-primary" />
          <p className="text-xl">Fetching Job Details...</p>
        </div>
      </div>
    );
  }

  // Derive filtered list here so both UI and Download handler can access it
  const filteredFindings = findings.filter(f => {
    if (filterClassification !== "all" && f.classification !== filterClassification) return false;
    if (filterSeverity !== "all" && f.severity?.toLowerCase() !== filterSeverity) return false;
    return true;
  });

  const triggerDownload = async (format: 'json' | 'pdf') => {
    if (format === 'json') {
      const dataStr = JSON.stringify(filteredFindings, null, 2);
      const blob = new Blob([dataStr], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `scan-findings-${job?.id?.slice(0,8) || 'export'}.json`;
      link.click();
      URL.revokeObjectURL(url);
    } else if (format === 'pdf') {
      // Dynamically import html2pdf so it doesn't break SSR
      const html2pdf = (await import('html2pdf.js')).default;

      const SEV_COLORS: Record<string, string> = {
        critical: '#dc2626', high: '#ea580c', medium: '#d97706',
        low: '#6b7280', info: '#3b82f6'
      };
      const SEV_BG: Record<string, string> = {
        critical: '#fef2f2', high: '#fff7ed', medium: '#fffbeb',
        low: '#f9fafb', info: '#eff6ff'
      };

      const filterSummary = [
        filterClassification !== 'all' ? filterClassification.replace('_', ' ') : null,
        filterSeverity !== 'all' ? filterSeverity : null
      ].filter(Boolean).join(', ') || 'All findings';

      const cardsHtml = filteredFindings.map(f => {
        const sev = f.severity?.toLowerCase() || 'info';
        const cls = (f.classification || 'unverified').replace('_', ' ');
        return `
          <div style="border:1.5px solid #e5e7eb; border-radius:10px; margin-bottom:18px; overflow:hidden; page-break-inside:avoid; background:#fff;">
            <div style="padding:16px 20px; border-bottom:1px solid #f1f5f9; display:flex; justify-content:space-between; align-items:flex-start; gap: 12px;">
              <div style="display:flex; flex-wrap:wrap; gap:8px; flex:1; min-width:0; align-items:center;">
                <span style="display:inline-block; line-height:1.4; background:${SEV_COLORS[sev]}; color:#fff; font-size:10px; font-weight:700; padding:3px 8px; border-radius:5px; text-transform:uppercase; white-space:nowrap;">${sev}</span>
                <span style="display:inline-block; line-height:1.4; font-size:10px; background:#f1f5f9; color:#475569; padding:3px 8px; border-radius:4px; font-family:monospace; word-break:break-all;">${f.rule_id || 'UNKNOWN_RULE'}</span>
              </div>
              <span style="display:inline-block; line-height:1.4; font-size:10px; background:${sev === 'critical' || sev === 'high' ? '#fef2f2' : '#f1f5f9'}; color:${sev === 'critical' || sev === 'high' ? '#b91c1c' : '#475569'}; padding:3px 8px; border-radius:4px; font-weight:600; white-space:nowrap; flex-shrink:0; text-align:center;">${cls}</span>
            </div>
            <div style="padding:14px 20px;">
              <div style="font-size:14px; font-weight:700; color:#111827; margin-bottom:6px;">
                ${f.finding_type === 'secret' ? 'Exposed Credential / Secret Key' : 'Security Vulnerability Detected'}
              </div>
              <div style="font-size:11px; color:#6b7280; margin-bottom:10px; font-family:monospace;">
                ${f.file_path || 'N/A'}${f.line_start ? ' · Line ' + f.line_start : ''}
              </div>
              ${f.explanation ? `<div style="font-size:12px; color:#374151; line-height:1.6; background:#f9fafb; padding:12px; border-radius:6px;">${f.explanation}</div>` : ''}
            </div>
          </div>`;
      }).join('');

      const html = `
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; padding: 32px; max-width: 760px; background-color: #ffffff;">
          <div style="border-bottom: 2px solid #059669; padding-bottom: 16px; margin-bottom: 24px;">
            <div style="font-size:11px; color:#059669; font-weight:700; text-transform:uppercase; letter-spacing:0.1em; margin-bottom:4px;">SENTINFI · SCAN REPORT</div>
            <h1 style="font-size:22px; font-weight:800; color:#111827; margin:0 0 4px;">${jobDetails.title}</h1>
            <div style="font-size:12px; color:#6b7280;">${jobDetails.subtitle} · ${new Date(job?.created_at).toLocaleString()}</div>
          </div>
          <div style="display:flex; gap:16px; margin-bottom:24px; flex-wrap:wrap;">
            <div style="background:#f0fdf4; border:1px solid #bbf7d0; border-radius:8px; padding:10px 16px;">
              <div style="font-size:10px; color:#15803d; font-weight:600; margin-bottom:2px;">FILTER APPLIED</div>
              <div style="font-size:13px; font-weight:700; color:#166534;">${filterSummary}</div>
            </div>
            <div style="background:#f9fafb; border:1px solid #e5e7eb; border-radius:8px; padding:10px 16px;">
              <div style="font-size:10px; color:#6b7280; font-weight:600; margin-bottom:2px;">FINDINGS IN REPORT</div>
              <div style="font-size:13px; font-weight:700; color:#111827;">${filteredFindings.length}</div>
            </div>
          </div>
          ${cardsHtml}
          <div style="margin-top:24px; padding-top:16px; border-top:1px solid #e5e7eb; font-size:10px; color:#9ca3af; text-align:center;">
            Generated by SentinFI AI Security Scanner · ${new Date().toLocaleString()}
          </div>
        </div>`;

      await html2pdf().set({
        margin: 12,
        filename: `scan-report-${job?.id?.slice(0,8) || 'export'}.pdf`,
        image: { type: 'jpeg', quality: 0.98 },
        html2canvas: { 
          scale: 2, 
          useCORS: true, 
          backgroundColor: '#ffffff', 
          logging: false,
          ignoreElements: (node: HTMLElement) => {
            const tag = node.tagName?.toUpperCase();
            return tag === 'STYLE' || tag === 'LINK' || tag === 'NOSCRIPT';
          }
        },
        jsPDF: { unit: 'pt', format: 'a4', orientation: 'portrait' },
      }).from(html).save();
    }
  };

  return (
    <div 
      className="h-full overflow-y-auto bg-neutral-50 px-8 py-6 pb-24 print:bg-white print:p-0"
      style={{
        backgroundImage: "linear-gradient(to right, #e2e8f0 1px, transparent 1px), linear-gradient(to bottom, #e2e8f0 1px, transparent 1px)",
        backgroundSize: "40px 40px"
      }}
    >
      <div className="max-w-6xl mx-auto space-y-6">
        
        {/* Navigation & Header */}
        <div className="print-hidden">
          <button 
            onClick={() => router.push("/")}
            className="flex items-center text-sm text-gray-500 hover:text-gray-900 transition-colors mb-6 font-medium"
          >
            <ArrowLeft className="w-4 h-4 mr-2" /> Back to overview
          </button>
          
          <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-widest font-bold text-emerald-600 mb-1">{job?.input_channel?.toUpperCase()} ANALYSIS</p>
              <h1 className="text-4xl font-black text-gray-900 tracking-tight">{jobDetails.title}</h1>
              <p className="text-sm text-gray-500 mt-2 font-medium">
                {jobDetails.subtitle} <span className="mx-2">·</span> submitted {job ? new Date(job.created_at).toLocaleString(undefined, {month:'short', day:'numeric', year:'numeric', hour:'numeric', minute:'2-digit'}) : ''}
              </p>
            </div>
            <Button className="rounded-full bg-white text-gray-900 border shadow-sm hover:bg-gray-50 h-10 px-6 font-semibold" onClick={() => document.getElementById('findings-section')?.scrollIntoView({ behavior: 'smooth'})}>
              <Search className="w-4 h-4 mr-2 text-gray-500" /> View findings
            </Button>
          </div>
        </div>

        {/* Dashboard Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          
          {/* Main Left Column */}
          <div className="md:col-span-2 space-y-6">
            
            {/* Pipeline Status Card */}
            <Card className="shadow-sm border-0 ring-1 ring-black/5 rounded-2xl overflow-hidden bg-white">
              <div className="p-6">
                <div className="flex items-center justify-between mb-8">
                  <h3 className="text-[11px] font-bold tracking-widest text-gray-400 uppercase">PIPELINE STATUS</h3>
                  <RefreshCw className={`w-4 h-4 text-emerald-500 ${job?.status !== 'completed' && job?.status !== 'failed' && job?.status !== 'rejected' ? 'animate-spin' : ''}`} />
                </div>
                
                <div className="flex items-center gap-3 mb-6">
                  <div className="inline-flex items-center justify-center px-3 py-1 rounded-full bg-gray-100 border border-gray-200">
                    <Clock className="w-3.5 h-3.5 mr-2 text-gray-500" />
                    <span className="text-xs font-bold text-gray-700 capitalize">{job?.status}</span>
                  </div>
                  <span className="text-sm text-gray-500 font-medium capitalize">{job?.status}</span>
                </div>

                {job?.status && <PipelineStatusBar currentStatus={job.status} />}
              </div>
            </Card>

            {/* Findings Summary Card */}
            <Card className="shadow-sm border-0 ring-1 ring-black/5 rounded-2xl bg-white">
              <div className="p-6 pb-4">
                <h3 className="text-base font-bold text-gray-900">Findings summary</h3>
                <p className="text-sm text-gray-500 mb-6">Severity distribution from the latest analysis pass.</p>
                
                <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-5 divide-y sm:divide-y-0 sm:divide-x divide-gray-100 border-t border-gray-100 -mx-6 px-4">
                  <div className="py-4 sm:py-6 px-4 flex flex-col">
                    <span className="text-sm font-semibold text-gray-600 mb-2">Critical</span>
                    <span className="text-4xl font-black text-gray-900">{report?.critical_count || 0}</span>
                  </div>
                  <div className="py-4 sm:py-6 px-4 flex flex-col">
                    <span className="text-sm font-semibold text-gray-600 mb-2">High</span>
                    <span className="text-4xl font-black text-gray-900">{report?.high_count || 0}</span>
                  </div>
                  <div className="py-4 sm:py-6 px-4 flex flex-col">
                    <span className="text-sm font-semibold text-gray-600 mb-2">Medium</span>
                    <span className="text-4xl font-black text-gray-900">{report?.medium_count || 0}</span>
                  </div>
                  <div className="py-4 sm:py-6 px-4 flex flex-col">
                    <span className="text-sm font-semibold text-gray-600 mb-2">Low</span>
                    <span className="text-4xl font-black text-gray-900">{report?.low_count || 0}</span>
                  </div>
                  <div className="py-4 sm:py-6 px-4 flex flex-col sm:hidden lg:flex">
                    <span className="text-sm font-semibold text-gray-600 mb-2">Info</span>
                    <span className="text-4xl font-black text-gray-900">{report?.info_count || 0}</span>
                  </div>
                </div>
              </div>
            </Card>
          </div>

          {/* Right Sidebar Column */}
          <div className="space-y-6">
            
            {/* Metadata Card */}
            <Card className="shadow-sm border-0 ring-1 ring-black/5 rounded-2xl bg-white max-w-sm">
              <div className="p-6">
                <h3 className="text-[11px] font-bold tracking-widest text-gray-400 uppercase mb-5">SCAN METADATA</h3>
                <div className="space-y-4">
                  <div className="flex justify-between items-center text-sm">
                    <span className="text-gray-500 font-medium">Job ID</span>
                    <span className="font-mono font-semibold text-gray-900 truncate max-w-[150px]">{job?.id}</span>
                  </div>
                  <div className="flex justify-between items-center text-sm">
                    <span className="text-gray-500 font-medium">Channel</span>
                    <span className="font-semibold text-gray-900">{job?.input_channel}</span>
                  </div>
                  <div className="flex justify-between items-center text-sm">
                    <span className="text-gray-500 font-medium">Started</span>
                    <span className="font-semibold text-gray-900 truncate">{job?.created_at ? new Date(job.created_at).toLocaleString(undefined, {month:'short', day:'numeric', year:'numeric', hour:'numeric', minute:'2-digit'}) : '—'}</span>
                  </div>
                  <div className="flex justify-between items-center text-sm">
                    <span className="text-gray-500 font-medium">Completed</span>
                    <span className="font-semibold text-gray-900">{report?.generated_at ? new Date(report.generated_at).toLocaleString(undefined, {hour:'numeric', minute:'2-digit'}) : '—'}</span>
                  </div>
                  <div className="flex justify-between items-center text-sm pt-3 border-t border-gray-100">
                    <span className="text-gray-500 font-medium">Total findings</span>
                    <span className="font-bold text-gray-900">{report?.total_findings ?? 0}</span>
                  </div>
                </div>
              </div>
            </Card>

            {/* AI Callout Card */}
            <div className="rounded-2xl bg-emerald-50/80 border border-emerald-100 p-6 print-hidden">
              <h3 className="flex items-center text-sm font-bold text-emerald-800 mb-3">
                <Sparkles className="w-4 h-4 mr-2 text-emerald-600" /> AI-assisted triage
              </h3>
              <p className="text-sm text-emerald-700/80 leading-relaxed font-medium mb-4">
                Findings are enriched with confidence and classification to focus analyst review where it matters.
              </p>
              <button 
                onClick={() => document.getElementById('findings-section')?.scrollIntoView({ behavior: 'smooth'})}
                className="text-sm font-bold text-emerald-800 hover:text-emerald-900 flex items-center transition-colors">
                Review triage queue <ArrowLeft className="w-3.5 h-3.5 ml-1 rotate-180" />
              </button>
            </div>
            
          </div>
        </div>

         {/* Findings Section */}
         <div id="findings-section" className="pt-12">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
              <h2 className="text-2xl font-black text-gray-900">Verified Findings</h2>
              <div className="flex items-center gap-3 print-hidden">
                 <Select value={filterClassification} onValueChange={(val) => setFilterClassification(val || "all")}>
                   <SelectTrigger className="w-[180px] bg-white border-gray-200 text-gray-700 font-medium focus:ring-emerald-500/20 shadow-sm transition-all h-10">
                     <SelectValue placeholder="Classification" />
                   </SelectTrigger>
                   <SelectContent>
                     <SelectItem value="all">All Classifications</SelectItem>
                     <SelectItem value="true_positive">True Positive</SelectItem>
                     <SelectItem value="false_positive">False Positive</SelectItem>
                     <SelectItem value="unverified">Unverified</SelectItem>
                   </SelectContent>
                 </Select>
                 
                 <Select value={filterSeverity} onValueChange={(val) => setFilterSeverity(val || "all")}>
                   <SelectTrigger className="w-[150px] bg-white border-gray-200 text-gray-700 font-medium focus:ring-emerald-500/20 shadow-sm transition-all h-10">
                     <SelectValue placeholder="Severity" />
                   </SelectTrigger>
                   <SelectContent>
                     <SelectItem value="all">All Severities</SelectItem>
                     <SelectItem value="critical">Critical</SelectItem>
                     <SelectItem value="high">High</SelectItem>
                     <SelectItem value="medium">Medium</SelectItem>
                     <SelectItem value="low">Low</SelectItem>
                     <SelectItem value="info">Info</SelectItem>
                   </SelectContent>
                 </Select>

                 <div className="flex items-center bg-white rounded-lg gap-0 border border-gray-200 shadow-sm h-10 overflow-hidden ml-2">
                   <button 
                     onClick={() => triggerDownload('pdf')} 
                     disabled={filteredFindings.length === 0}
                     className="px-3 hover:bg-gray-50 flex items-center gap-1.5 text-sm font-medium border-r border-gray-200 text-gray-700 h-full disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                   >
                     <Download className="w-4 h-4" /> PDF
                   </button>
                   <button 
                     onClick={() => triggerDownload('json')} 
                     disabled={filteredFindings.length === 0}
                     className="px-3 hover:bg-gray-50 flex items-center gap-1.5 text-sm font-medium text-gray-700 h-full disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                   >
                     JSON
                   </button>
                 </div>
              </div>
            </div>
            
            {(() => {
               if (findings.length === 0) {
                return (
                  <div className="flex flex-col items-center justify-center p-16 text-center bg-white rounded-2xl border border-dashed border-gray-300">
                     <ShieldCheck className="w-16 h-16 text-emerald-400 mb-6" />
                     <h3 className="text-2xl font-bold text-gray-900 mb-2">No Vulnerabilities Found</h3>
                     <p className="text-gray-500 max-w-sm font-medium">
                       {job?.status === 'completed' 
                         ? "This target analysis returned completely clean. No security issues were detected by any stage in the pipeline."
                         : "The analysis engine is evaluating the target source code. Results will appear here dynamically."}
                     </p>
                  </div>
                );
              }

              if (filteredFindings.length === 0) {
                return (
                  <div className="flex flex-col items-center justify-center p-16 text-center bg-white rounded-2xl border border-dashed border-gray-300">
                     <Search className="w-12 h-12 text-gray-300 mb-4" />
                     <h3 className="text-lg font-bold text-gray-900 mb-2">No matches found</h3>
                     <p className="text-gray-500 max-w-sm font-medium text-sm">
                       Try adjusting your filters to see more findings.
                     </p>
                     <Button variant="outline" className="mt-4" onClick={() => { setFilterClassification("all"); setFilterSeverity("all"); }}>
                       Clear Filters
                     </Button>
                  </div>
                );
              }

               return (
                 <div className="space-y-6">
                    {filteredFindings.map((finding) => (
                     <Card key={finding.id} className="finding-card shadow-sm border-0 ring-1 ring-black/10 rounded-xl overflow-hidden bg-white hover:ring-black/20 transition-all">
                       <div className="border-b border-gray-100 p-6 pb-4">
                          <div className="flex items-center justify-between mb-3">
                               <div className="flex items-center gap-3">
                                  {finding.severity?.toLowerCase() === 'critical' && <Badge className="bg-red-600 hover:bg-red-700 font-bold uppercase rounded-md text-[10px] px-2 py-0.5">Critical</Badge>}
                                  {finding.severity?.toLowerCase() === 'high' && <Badge className="bg-orange-500 hover:bg-orange-600 font-bold uppercase rounded-md text-[10px] px-2 py-0.5 text-white">High</Badge>}
                                  {finding.severity?.toLowerCase() === 'medium' && <Badge className="bg-yellow-400 hover:bg-yellow-500 font-bold uppercase rounded-md text-[10px] px-2 py-0.5 text-yellow-950">Medium</Badge>}
                                  {finding.severity?.toLowerCase() === 'low' && <Badge variant="outline" className="border-gray-200 text-gray-600 font-bold uppercase rounded-md text-[10px] px-2 py-0.5">Low</Badge>}
                                  
                                  <span className="text-xs font-mono bg-gray-100 text-gray-600 px-2 py-0.5 rounded border border-gray-200">{finding.rule_id || 'UNKNOWN_RULE'}</span>
                               </div>
                               
                               <Badge variant={finding.classification === 'true_positive' ? 'default' : 'secondary'} className={finding.classification === 'true_positive' ? "bg-red-50 text-red-700 border border-red-100 font-semibold" : "bg-gray-100 text-gray-600 border border-gray-200 font-semibold"}>
                                  {finding.classification.replace('_', ' ')}
                               </Badge>
                          </div>
                          
                          <h4 className="text-lg font-bold text-gray-900">
                             {finding.finding_type === 'secret' ? 'Exposed Credential / Secret Key' : 'Security Vulnerability Detected'}
                          </h4>
                          
                          <div className="flex items-center text-sm text-gray-500 mt-2 gap-2">
                             <FileCode className="w-4 h-4 text-gray-400" />
                             <span className="font-mono text-gray-600">{finding.file_path || "N/A"}</span>
                             {finding.line_start && (
                                <>
                                  <span className="text-gray-300">|</span>
                                  <span>Line {finding.line_start} {finding.line_end && finding.line_end !== finding.line_start && `- ${finding.line_end}`}</span>
                                </>
                             )}
                          </div>
                       </div>
                       
                       <div className="p-6 bg-gray-50/50">
                          <h5 className="text-[11px] font-bold uppercase tracking-widest text-gray-500 mb-2">AI EXPLANATION</h5>
                          <p className="text-sm text-gray-700 leading-relaxed max-w-4xl">
                             {finding.explanation || "No AI explanation available."}
                          </p>
                          
                          {finding.code_snippet && (
                             <div className="mt-6">
                                <h5 className="text-[11px] font-bold uppercase tracking-widest text-gray-500 mb-2">VULNERABLE CONTEXT</h5>
                                <div className="bg-[#1e1e1e] rounded-lg p-5 overflow-x-auto text-xs font-mono text-gray-300 shadow-inner">
                                   <pre><code>{finding.code_snippet}</code></pre>
                                </div>
                             </div>
                          )}
                          
                          {finding.suggested_fix && (
                             <div className="mt-6">
                                <h5 className="text-[11px] font-bold uppercase tracking-widest text-emerald-600 mb-2">SUGGESTED REMEDIATION</h5>
                                <div className="bg-emerald-950/5 border border-emerald-900/10 rounded-lg p-5 overflow-x-auto text-xs font-mono text-emerald-800 shadow-inner">
                                   <pre><code>{finding.suggested_fix}</code></pre>
                                </div>
                             </div>
                          )}
                       </div>
                    </Card>
                 ))}
              </div>
           );
           })()}
        </div>

      </div>
    </div>
  );
}
// Add to lucide-react imports: Clock
