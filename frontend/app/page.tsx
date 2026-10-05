"use client";
import { Zap } from "lucide-react";
import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ScanActivityList } from "@/components/scan-activity-list";
import { PipelineSidebar } from "@/components/pipeline-sidebar";
import { InitiateScanModal } from "@/components/initiate-scan-modal";
import { supabase } from "@/lib/supabase";

export default function Home() {
  const [metrics, setMetrics] = useState({ total: 0, active: 0, completed: 0, critical: 0, high: 0 });

  useEffect(() => {
    let intervalId: NodeJS.Timeout;

    const fetchMetrics = async () => {
      const { data, error } = await supabase
        .from('scan_jobs')
        .select('status, reports(*)')
        .eq("user_id", "c5f01e76-49b6-4234-9eac-dda501ca577c");

      if (error) {
        console.error("Dashboard overview metrics fetch error:", error);
        // Only stop polling on hard auth or syntax errors, not network drops
        if (error.code === '401' || error.code === '400') {
           clearInterval(intervalId);
        }
        return;
      }

      if (data) {
        let total = data.length;
        let active = 0;
        let completed = 0;
        let critical = 0;
        let high = 0;
        const activeStates = ["queued", "validating", "preparing", "cloning", "extracting", "crawling", "scanning", "triaging"];

        data.forEach((job: any) => {
          if (activeStates.includes(job.status)) active++;
          if (job.status === "completed") completed++;

          let reportObj = null;
          if (Array.isArray(job.reports)) {
            reportObj = job.reports.length > 0 ? job.reports[0] : null;
          } else {
            reportObj = job.reports; // Supabase 1:1 mapped as object
          }
          
          if (reportObj) {
            critical += (reportObj.critical_count || 0);
            high += (reportObj.high_count || 0);
          }
        });

        setMetrics({ total, active, completed, critical, high });
      }
    };

    fetchMetrics();
    intervalId = setInterval(fetchMetrics, 5000);
    return () => clearInterval(intervalId);
  }, []);

  return (
    <div className="flex-1 overflow-y-auto p-8 relative">
      <div className="max-w-7xl mx-auto space-y-8">
        
        {/* Header Section */}
        <div className="flex items-start justify-between">
          <div>
            <p className="text-xs font-bold text-gray-500 tracking-widest uppercase mb-1">Command Center</p>
            <h1 className="text-3xl font-bold text-gray-900">Overview</h1>
            <p className="text-gray-500 text-sm mt-1">A clear view of what is running, what needs attention, and what changed recently.</p>
          </div>
          <InitiateScanModal />
        </div>

        {/* Analytics Row */}
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          <Card className="shadow-sm border-gray-100">
            <CardHeader className="p-4 pb-2">
              <CardTitle className="text-xs font-semibold text-gray-500">Total scans</CardTitle>
            </CardHeader>
            <CardContent className="p-4 pt-0">
              <div className="text-2xl font-bold">{metrics.total}</div>
              <p className="text-xs text-gray-400 mt-1">All channels, this workspace</p>
            </CardContent>
          </Card>
          
          <Card className="shadow-sm border-gray-100">
            <CardHeader className="p-4 pb-2">
              <CardTitle className="text-xs font-semibold text-gray-500 flex justify-between">
                Active scans
                {metrics.active > 0 && (
                  <div className="text-emerald-500 flex h-2 w-2 relative mt-1">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                  </div>
                )}
              </CardTitle>
            </CardHeader>
            <CardContent className="p-4 pt-0">
              <div className="text-2xl font-bold text-gray-900">{metrics.active}</div>
              <p className="text-xs text-gray-400 mt-1">{metrics.active > 0 ? "Currently in pipeline" : "Idle"}</p>
            </CardContent>
          </Card>
          
          <Card className="shadow-sm border-gray-100">
            <CardHeader className="p-4 pb-2">
              <CardTitle className="text-xs font-semibold text-gray-500 flex justify-between">
                Completed
                <div className="w-4 h-4 rounded-full bg-blue-50 text-blue-500 flex items-center justify-center text-[10px]">✓</div>
              </CardTitle>
            </CardHeader>
            <CardContent className="p-4 pt-0">
              <div className="text-2xl font-bold">{metrics.completed}</div>
              <p className="text-xs text-gray-400 mt-1">Ready for review</p>
            </CardContent>
          </Card>
          
          <Card className="shadow-sm border-gray-100">
            <CardHeader className="p-4 pb-2">
              <CardTitle className="text-xs font-semibold text-gray-500 flex justify-between">
                Critical findings
                <div className="w-5 h-5 rounded-full bg-red-50 text-red-600 flex items-center justify-center font-bold text-[10px]">!</div>
              </CardTitle>
            </CardHeader>
            <CardContent className="p-4 pt-0">
              <div className="text-2xl font-bold text-red-600">{metrics.critical}</div>
              <p className="text-xs text-gray-400 mt-1">Immediate attention</p>
            </CardContent>
          </Card>
          
          <Card className="shadow-sm border-gray-100">
            <CardHeader className="p-4 pb-2">
              <CardTitle className="text-xs font-semibold text-gray-500 flex justify-between">
                High findings
                <div className="w-5 h-5 rounded-full bg-orange-50 text-orange-500 flex items-center justify-center font-bold text-[10px] uppercase">A</div>
              </CardTitle>
            </CardHeader>
            <CardContent className="p-4 pt-0">
              <div className="text-2xl font-bold text-orange-500">{metrics.high}</div>
              <p className="text-xs text-gray-400 mt-1">Prioritize next</p>
            </CardContent>
          </Card>
        </div>

        {/* Content Split Area */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2">
            <ScanActivityList />
          </div>
          <div className="lg:col-span-1">
            <PipelineSidebar />
          </div>
        </div>
        
      </div>
    </div>
  );
}