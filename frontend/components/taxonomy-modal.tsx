"use client";

import { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Search, BookOpen } from "lucide-react";
import { Input } from "@/components/ui/input";

export function TaxonomyModal({ customTrigger }: { customTrigger?: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const [filterCategory, setFilterCategory] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");

  const taxonomies = [
    { id: "ID #1", category: ["live url"], code: "dom_xss", label: "DOM-Based & Reflected XSS", desc: "Client-side XSS vulnerabilities." },
    { id: "ID #2", category: ["github", "zip file"], code: "exposed_secrets_js", label: "Exposed Secrets in JavaScript", desc: "Hardcoded API keys/JWTs in frontend code." },
    { id: "ID #3", category: ["live url"], code: "broken_access_control", label: "Broken Access Control", desc: "Insecure endpoints or missing authorization." },
    { id: "ID #4", category: ["live url"], code: "security_misconfig", label: "Security Misconfiguration", desc: "Missing security headers or debug exposures." },
    { id: "ID #5", category: ["live url"], code: "info_leakage", label: "Information Leakage", desc: "Exposure of sensitive infrastructure or PII." },
    { id: "ID #10", category: ["docker"], code: "insecure_base_image", label: "Insecure Base Image", desc: "Obsolete or vulnerable container base image." },
    { id: "ID #11", category: ["docker"], code: "privilege_escalation_root", label: "Root Execution Privileges", desc: "Container running as root user." },
    { id: "ID #12", category: ["docker"], code: "baked_in_secret", label: "Baked-in Credentials & Secrets", desc: "Secrets embedded in image layers." },
    { id: "ID #13", category: ["docker", "github", "zip file"], code: "dependency_cve", label: "Dependency / OS CVE", desc: "High/Critical CVE in OS package or dependency." },
    { id: "ID #14", category: ["docker", "github"], code: "missing_security_config", label: "Missing Security Configuration", desc: "Missing specific secure workload settings." }
  ];

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      {customTrigger ? (
        <DialogTrigger className="w-full text-left bg-transparent border-none appearance-none cursor-pointer">
          {customTrigger}
        </DialogTrigger>
      ) : (
        <DialogTrigger className="inline-flex items-center justify-center text-sm rounded-lg bg-emerald-800 text-white px-6 h-9 font-medium shadow-sm transition-colors cursor-pointer">
          Taxonomy
        </DialogTrigger>
      )}
      
      <DialogContent className="sm:max-w-4xl overflow-hidden p-0 rounded-2xl flex flex-col gap-0 border-gray-100 shadow-xl bg-white h-[80vh]">
        
        <DialogHeader className="p-6 pb-4 border-b shrink-0 bg-white">
          <div className="flex items-center gap-3 mb-6">
             <div className="w-10 h-10 rounded-xl bg-gray-50 border flex items-center justify-center text-gray-500">
               <BookOpen className="w-5 h-5" />
             </div>
             <div>
               <DialogTitle className="text-xl font-bold font-sans">Vulnerability Taxonomy & Catalog</DialogTitle>
               <p className="text-sm text-gray-500 mt-1">Database of vulnerability classes across all channels</p>
             </div>
          </div>

          <div className="flex items-center justify-between gap-4">
             <Tabs value={filterCategory} onValueChange={setFilterCategory} className="flex-1">
                <TabsList className="bg-transparent space-x-2 h-9 p-0">
                  {['All', 'GitHub', 'Live URL', 'ZIP File', 'Docker'].map((tab) => (
                    <TabsTrigger 
                      key={tab} 
                      value={tab.toLowerCase()} 
                      className="rounded-full px-4 text-xs font-medium data-[state=active]:bg-gray-100 data-[state=active]:shadow-none data-[state=active]:text-gray-900 text-gray-500"
                    >
                      {tab}
                    </TabsTrigger>
                  ))}
                </TabsList>
             </Tabs>

             <div className="relative shrink-0 w-64">
               <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
               <Input 
                 className="pl-9 h-9 w-full text-sm rounded-lg bg-gray-50/50 border-gray-200"
                 placeholder="Search taxonomy..."
                 value={searchQuery}
                 onChange={(e) => setSearchQuery(e.target.value)}
               />
             </div>
          </div>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto bg-gray-50/30 p-6 space-y-3">
          {(() => {
             const filtered = taxonomies.filter((item) => {
               if (filterCategory !== "all" && !item.category.includes(filterCategory)) return false;
               if (searchQuery) {
                  const q = searchQuery.toLowerCase();
                  if (!item.code.toLowerCase().includes(q) && 
                      !item.label.toLowerCase().includes(q) && 
                      !item.desc.toLowerCase().includes(q)) {
                    return false;
                  }
               }
               return true;
             });

             if (filtered.length === 0) {
               return (
                  <div className="p-8 text-center text-sm text-gray-500 bg-white rounded-xl border border-dashed border-gray-300">
                    No taxonomy classes match your search query.
                  </div>
               );
             }

             return filtered.map((item) => (
                <div key={item.id} className="bg-white border rounded-xl p-5 shadow-sm">
                   <div className="flex items-start justify-between mb-2">
                      <div className="flex flex-wrap items-center gap-2">
                         <span className="font-mono text-sm font-bold text-gray-900">{item.code}</span>
                         <span className="text-gray-400">·</span>
                         <span className="text-sm font-semibold text-gray-700">{item.label}</span>
                      </div>
                      <div className="shrink-0 bg-gray-50 text-gray-500 text-[10px] font-bold px-2 py-1 rounded border tracking-wider">
                         {item.id}
                      </div>
                   </div>
                   <p className="text-sm text-gray-500">{item.desc}</p>
                </div>
             ));
          })()}
        </div>

      </DialogContent>
    </Dialog>
  );
}
