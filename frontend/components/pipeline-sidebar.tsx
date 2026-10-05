"use client";

import { useEffect, useState } from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { supabase } from "@/lib/supabase";
import { Loader2 } from "lucide-react";

export function PipelineSidebar() {
  const [pipelines, setPipelines] = useState<any[]>([]);

  useEffect(() => {
    let intervalId: NodeJS.Timeout;

    const fetchActivePipelines = async () => {
      const { data, error } = await supabase
        .from("scan_jobs")
        .select("*, github_job_details(*)")
        .eq("user_id", "c5f01e76-49b6-4234-9eac-dda501ca577c")
        .in("status", ["queued", "validating", "preparing", "cloning", "extracting", "crawling", "scanning", "triaging"])
        .order("created_at", { ascending: false });

      if (error) {
        // Stop polling on error
        clearInterval(intervalId);
        return;
      }

      if (data) {
        // Map data to the format expected by the UI
        const mapped = data.map((job) => {
          let name = job.id;
          if (job.input_channel === "github" && job.github_job_details?.length > 0) {
            name = `${job.github_job_details[0].repo_owner}/${job.github_job_details[0].repo_name}`;
          }
          return {
            id: job.id,
            name: name,
            status: job.status,
            channel: job.input_channel
          };
        });
        setPipelines(mapped);
      }
    };

    // Initial fetch
    fetchActivePipelines();

    // Poll every 3 seconds for live updates (MVP approach instead of WebSocket config)
    intervalId = setInterval(fetchActivePipelines, 3000);
    return () => clearInterval(intervalId);
  }, []);

  const steps = ["queued", "validating", "cloning", "scanning", "triaging", "completed"];

  return (
    <Card className="shadow-sm border-gray-100">
      <CardHeader className="p-5 pb-4 border-b bg-white">
        <CardTitle className="text-base font-semibold flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></div>
          Pipeline now
        </CardTitle>
        <p className="text-xs text-gray-500 font-normal">Active jobs tracking across nodes.</p>
      </CardHeader>
      <CardContent className="p-0 bg-white">
        <div className="divide-y">
          {pipelines.map((job, idx) => {
            const currentStepIdx = steps.indexOf(job.status);
            return (
              <div key={idx} className="p-5 hover:bg-gray-50 transition-colors">
                <div className="flex justify-between items-center mb-4">
                  <span className="text-sm font-semibold truncate pr-4 text-gray-900">• {job.name}</span>
                  <span className="uppercase text-[10px] font-bold tracking-wider text-gray-500">{job.channel}</span>
                </div>
                
                {/* Discrete Stepper */}
                <div className="flex items-center justify-between gap-1 w-full relative">
                   <div className="absolute top-1/2 left-0 right-0 h-0.5 bg-gray-100 -translate-y-1/2 z-0"></div>
                   {steps.map((s, stepIndex) => {
                      const isActive = stepIndex === currentStepIdx;
                      const isPast = stepIndex < currentStepIdx;
                      
                      return (
                        <div key={s} className="relative z-10 flex flex-col items-center gap-1 group">
                          <div className={`w-3 h-3 rounded-full border-2 bg-white transition-colors
                            ${isActive ? 'border-emerald-500 animate-pulse shadow-[0_0_8px_rgba(16,185,129,0.5)]' : 
                              isPast ? 'border-emerald-500 bg-emerald-500' : 'border-gray-200'}
                          `}></div>
                          
                          {isActive && (
                            <div className="absolute top-4 whitespace-nowrap text-[9px] font-bold text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded uppercase tracking-widest">
                              {s}
                            </div>
                          )}
                        </div>
                      );
                   })}
                </div>
                
                <div className="mt-8 flex justify-between items-center text-xs text-gray-500 font-medium">
                  {job.status === "completed" ? (
                    <span className="text-emerald-600 font-bold">Finished</span>
                  ) : job.status === "failed" || job.status === "rejected" ? (
                    <span className="text-rose-600 font-bold capitalize">{job.status}</span>
                  ) : (
                    <span className="flex items-center gap-1.5 capitalize text-emerald-800 font-bold">
                       <Loader2 className="w-3 h-3 animate-spin"/> {job.status}...
                    </span>
                  )}
                </div>
              </div>
            );
          })}
          
          {pipelines.length === 0 && (
             <div className="p-8 text-center text-sm text-gray-500">
               No active pipelines.
             </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
