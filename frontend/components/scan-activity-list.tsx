"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Search, GitBranch, Globe, FileArchive, Box, Trash2, Loader2 } from "lucide-react";
import { supabase } from "@/lib/supabase";

export function ScanActivityList() {
  const [activities, setActivities] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterType, setFilterType] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [isDeleting, setIsDeleting] = useState<string | null>(null);
  const router = useRouter();

  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    setIsDeleting(id);
    const { error } = await supabase.from('scan_jobs').delete().eq('id', id);
    if (!error) {
      setActivities(prev => prev.filter(a => a.id !== id));
    }
    setIsDeleting(null);
  };

  useEffect(() => {
    let intervalId: NodeJS.Timeout;

    const fetchHistory = async () => {
      const { data, error } = await supabase
        .from("scan_jobs")
        .select(`
          *,
          github_job_details(*),
          reports(*)
        `)
        .eq("user_id", "c5f01e76-49b6-4234-9eac-dda501ca577c")
        .order("created_at", { ascending: false });

      if (error) {
        // Stop polling on error
        clearInterval(intervalId);
        setLoading(false);
        return;
      }

      if (data) {
        const mapped = data.map((job) => {
          let name = job.id.split('-')[0];
          let url = "";
        
          if (job.input_channel === "github" && job.github_job_details) {
            const gh = Array.isArray(job.github_job_details) ? job.github_job_details[0] : job.github_job_details;
            if (gh) {
              name = `${gh.repo_owner}/${gh.repo_name}`;
              url = gh.repo_url;
            }
          }
          
          let findings = 0;
          if (job.reports) {
            const report = Array.isArray(job.reports) ? job.reports[0] : job.reports;
            if (report) {
              findings = report.total_findings ?? 0;
            }
          }
        
          const timeStr = new Date(job.created_at).toLocaleString(undefined, { 
             month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' 
          });
          
          let statusLabel = job.status;
          if (statusLabel) {
             statusLabel = statusLabel.charAt(0).toUpperCase() + statusLabel.slice(1);
          }
        
          return {
            id: job.id,
            name: name,
            url: url,
            type: job.input_channel,
            status: statusLabel,
            date: timeStr,
            findings: findings
          };
        });
        setActivities(mapped);
      }
      setLoading(false);
    };

    fetchHistory();
    intervalId = setInterval(fetchHistory, 5000);
    return () => clearInterval(intervalId);
  }, []);

  return (
    <>
      <div className="mb-4">
        <h2 className="text-lg font-bold text-gray-900">Recent scan activity</h2>
        <p className="text-sm text-gray-500">Your latest analysis jobs across all channels. Click to view or manage.</p>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
        {/* Toolbar */}
        <div className="px-2 py-3 border-b flex items-center justify-between gap-4 overflow-x-auto min-w-0">
          <Tabs value={filterType} onValueChange={setFilterType} className="w-[400px]">
            <TabsList className="bg-transparent space-x-1 h-9">
              {[
                { label: 'All', value: 'all' },
                { label: 'Live URL', value: 'url' },
                { label: 'Github', value: 'github' },
                { label: 'Zip', value: 'zip' },
                { label: 'Docker', value: 'docker' }
              ].map((tab) => (
                <TabsTrigger 
                  key={tab.value} 
                  value={tab.value} 
                  className="rounded-full px-4 text-xs font-medium data-[state=active]:bg-gray-100 data-[state=active]:shadow-none data-[state=active]:text-gray-900 text-gray-500"
                >
                  {tab.label}
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>
          
          <div className="relative shrink-0 pr-4">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <Input 
              className="pl-9 h-9 w-64 text-sm rounded-lg bg-gray-50/50 border-gray-200"
              placeholder="Search scans..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
        </div>

        {/* List */}
        <div className="divide-y">
          {(() => {
            const filteredActivities = activities.filter((item) => {
              if (filterType !== 'all' && item.type !== filterType) return false;
              if (searchQuery && !item.name.toLowerCase().includes(searchQuery.toLowerCase())) return false;
              return true;
            });
            
            if (loading) {
              return (
                <div className="p-8 flex justify-center items-center text-sm text-gray-500">
                  <Loader2 className="w-5 h-5 animate-spin mr-2" /> Loading history...
                </div>
              );
            }
            
            if (filteredActivities.length === 0) {
              return (
                 <div className="p-8 text-center text-sm text-gray-500">
                  No scans match your criteria.
                </div>
              );
            }
            
            return filteredActivities.map((item) => (
              <div 
                key={item.id} 
                className="p-4 hover:bg-gray-50 transition-colors flex items-center gap-4 group cursor-pointer"
                onClick={() => router.push(`/scan/${item.id}`)}
              >
                
                <div className="w-10 h-10 shrink-0 rounded-lg bg-blue-50 flex items-center justify-center text-blue-500">
                  {item.type === 'github' && <GitBranch className="w-5 h-5" />}
                  {item.type === 'url' && <Globe className="w-5 h-5 text-purple-500" />}
                  {item.type === 'zip' && <FileArchive className="w-5 h-5" />}
                  {item.type === 'docker' && <Box className="w-5 h-5" />}
                </div>
                
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-3 mb-1">
                    <h3 className="text-sm font-bold text-gray-900 truncate">{item.name}</h3>
                    
                    {item.status === 'Completed' && (
                      <span className="inline-flex items-center gap-1 text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-600 border border-emerald-100">
                        <span className="w-3 h-3 rounded-full flex items-center justify-center border border-current text-[8px] leading-none">✓</span>
                        {item.status}
                      </span>
                    )}
                    {(item.status === 'Rejected' || item.status === 'Failed') && (
                      <span className="inline-flex items-center gap-1 text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-rose-50 text-rose-600 border border-rose-100">
                        <span className="w-3 h-3 rounded-full flex items-center justify-center border border-current text-[8px] leading-none text-rose-600">✕</span>
                        {item.status}
                      </span>
                    )}
                    {item.status !== 'Completed' && item.status !== 'Rejected' && item.status !== 'Failed' && (
                      <span className="inline-flex items-center gap-1 text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-blue-50 text-blue-600 border border-blue-100">
                        <Loader2 className="w-3 h-3 animate-spin"/>
                        {item.status}
                      </span>
                    )}
                  </div>
                  
                  <div className="flex items-center text-xs text-gray-500 gap-2">
                    <span className="truncate max-w-sm">{item.url || "No URL"}</span>
                    <span>·</span>
                    <span className="shrink-0">{item.date}</span>
                  </div>
                </div>
                
                <div className="text-right shrink-0">
                  <div className="text-sm font-bold text-gray-900">{item.findings}</div>
                  <div className="text-xs text-gray-400">findings</div>
                </div>
                
                <button 
                  onClick={(e) => handleDelete(e, item.id)}
                  disabled={isDeleting === item.id}
                  className="opacity-0 group-hover:opacity-100 shrink-0 p-2 text-gray-400 hover:text-red-600 transition-all rounded-md disabled:opacity-50"
                >
                  {isDeleting === item.id ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
                </button>
                
                <div className="shrink-0 text-gray-300">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="9 18 15 12 9 6"></polyline></svg>
                </div>
              </div>
            ));
          })()}
        </div>
      </div>
    </>
  );
}
