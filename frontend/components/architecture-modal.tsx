"use client";

import { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Layers, Server, GitBranch, Globe, FileArchive, Box, Shield, Zap, Lock, Cpu } from "lucide-react";

export function ArchitectureModal({ customTrigger }: { customTrigger?: React.ReactNode }) {
  const [open, setOpen] = useState(false);

  const channels = [
    {
      id: "github",
      icon: <GitBranch className="w-4 h-4" />,
      label: "GitHub Repo",
      description: "Deep static analysis pipeline for cloned Git repositories.",
      steps: [
        { title: "Ingestion & Validation", desc: "Verifies repo read-access and GitHub URL formatting. Imposes 500MB clone size ceiling." },
        { title: "Secure Cloning Sandbox", desc: "Clones into a single-use ephemeral Docker container. Classic PATs stored purely in RAM with 5-minute TTL." },
        { title: "Static Scanning (SAST & SCA)", desc: "Triggers Semgrep for code vulnerabilities, Gitleaks for secrets, and dependency-audits for known CVEs. node_modules and builds excluded initially." },
        { title: "AI Contextual Triage", desc: "Uses Gemini/Groq for false-positive reduction. Sends symmetrical 50-line window (25 before/after) around findings." }
      ],
      invariants: [
        { icon: <Shield className="w-4 h-4 text-emerald-500" />, title: "Zero Retention", desc: "Code is wiped immediately post-scan." },
        { icon: <Lock className="w-4 h-4 text-emerald-700" />, title: "Ephemeral PATs", desc: "Tokens never touch the database or logs." }
      ]
    },
    {
      id: "url",
      icon: <Globe className="w-4 h-4" />,
      label: "Live URL",
      description: "Dynamic active analysis (DAST) for live web endpoints.",
      steps: [
        { title: "Edge Gatekeeper", desc: "Protects against SSRF loopbacks and duplicate active URLs. Validates 200 OK reachability." },
        { title: "Headless Crawl", desc: "Executes JavaScript bundles via Playwright to discover implicit endpoints and DOM-XSS vectors." },
        { title: "DAST Active Scanning", desc: "Injects standard payloads (SQLi, XSS) natively across discovered endpoints using ZAP engines." },
        { title: "AI Analysis", desc: "LLM verifies client-side JS bundles with up to 100,000 token context window." }
      ],
      invariants: [
        { icon: <Cpu className="w-4 h-4 text-purple-500" />, title: "No Source Code", desc: "Operates completely blindly from source code." },
        { icon: <Zap className="w-4 h-4 text-amber-500" />, title: "Hard Rate Limits", desc: "Enforces exponential backoff for aggressive crawling." }
      ]
    },
    {
      id: "zip",
      icon: <FileArchive className="w-4 h-4" />,
      label: "ZIP File",
      description: "Offline static analysis for compressed source code bundles.",
      steps: [
        { title: "Upload Gatekeeper", desc: "Enforces hard 50MB inclusive upload boundary. Verifies magic bytes (50 4B 03 04) to prevent spoofing." },
        { title: "Secure Extraction", desc: "Extracts contents into isolated ephemeral sandbox guarding against zip-slip path traversals and zip-bombs." },
        { title: "Static Scanning", desc: "Performs Semgrep and Gitleaks (working-tree-only) on extracted source code. Nested archives ignored." },
        { title: "AI Contextual Triage", desc: "LLM analyzes surrounding logic. Severity can only be downgraded from scanner baselines, never upgraded." }
      ],
      invariants: [
        { icon: <Lock className="w-4 h-4 text-red-500" />, title: "No Git History", desc: "Gitleaks is constrained strictly to the working tree." },
        { icon: <Shield className="w-4 h-4 text-emerald-500" />, title: "Sandbox Wipe", desc: "Extracted contents instantly deleted on completion." }
      ]
    },
    {
      id: "docker",
      icon: <Box className="w-4 h-4" />,
      label: "Docker",
      description: "Static topology and vulnerability scanning for container manifests.",
      steps: [
        { title: "Artifact Ingestion", desc: "Accepts 2MB max Dockerfile or polls public Docker Hub images via registry references." },
        { title: "Image Sandbox (DinD)", desc: "Pulls up to 1GB image within 5-minutes into an isolated nested daemon." },
        { title: "Static Inspection", desc: "Performs layer-by-layer static scanning. THE CONTAINER IS NEVER EXECUTED." },
        { title: "Misconfiguration Triage", desc: "AI maps misconfigurations to best practice remediations without actually running the app layer." }
      ],
      invariants: [
        { icon: <Shield className="w-4 h-4 text-rose-500" />, title: "No Execution", desc: "Target artifacts are strictly parsed, never 'run'." },
        { icon: <Zap className="w-4 h-4 text-amber-500" />, title: "Strict Match", desc: "Hard failure state on classification/artifact mismatch." }
      ]
    }
  ];

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      {customTrigger ? (
        <DialogTrigger className="w-full text-left bg-transparent border-none appearance-none cursor-pointer">
          {customTrigger}
        </DialogTrigger>
      ) : (
        <DialogTrigger className="inline-flex items-center justify-center text-sm rounded-lg bg-emerald-800 text-white px-6 h-9 font-medium shadow-sm transition-colors cursor-pointer">
          Architecture
        </DialogTrigger>
      )}
      
      <DialogContent className="sm:max-w-4xl max-h-[85vh] overflow-hidden p-0 rounded-2xl flex flex-col gap-0 border-gray-100 shadow-xl bg-white">
        
        <DialogHeader className="p-6 pb-4 border-b bg-white relative z-10 shrink-0">
          <div className="flex items-center gap-3">
             <div className="w-10 h-10 rounded-xl bg-gray-50 border flex items-center justify-center text-emerald-600">
               <Layers className="w-5 h-5" />
             </div>
             <div>
               <DialogTitle className="text-xl font-bold font-sans">Platform Architecture</DialogTitle>
               <p className="text-sm text-gray-500 mt-1">Select an input channel to view its pipeline execution flow and invariants.</p>
             </div>
          </div>
        </DialogHeader>

        <div className="flex-1 overflow-hidden flex flex-col bg-gray-50/30 min-h-0">
          <Tabs defaultValue="github" className="w-full h-full flex flex-col min-h-0">
            
            <div className="px-6 pt-4 border-b bg-white shrink-0">
              <TabsList className="bg-transparent space-x-6 h-auto p-0 mb-[-1px]">
                {channels.map((ch) => (
                  <TabsTrigger 
                    key={ch.id} 
                    value={ch.id} 
                    className="flex items-center gap-2 rounded-none border-b-2 border-transparent px-2 py-3 text-sm font-medium text-gray-500 hover:text-gray-700 data-[state=active]:border-emerald-500 data-[state=active]:text-emerald-700 data-[state=active]:bg-transparent shadow-none data-[state=active]:shadow-none transition-colors"
                  >
                    {ch.icon}
                    {ch.label}
                  </TabsTrigger>
                ))}
              </TabsList>
            </div>
            
            <div className="flex-1 overflow-y-auto p-6 min-h-0 [&::-webkit-scrollbar]:w-2 [&::-webkit-scrollbar-track]:bg-transparent [&::-webkit-scrollbar-thumb]:bg-gray-200 [&::-webkit-scrollbar-thumb]:rounded-full hover:[&::-webkit-scrollbar-thumb]:bg-gray-300">
              {channels.map((ch) => (
                <TabsContent key={ch.id} value={ch.id} className="mt-0 space-y-8 animate-in fade-in slide-in-from-bottom-2 focus:outline-none">
                  
                  {/* Overview Text */}
                  <div>
                    <h3 className="text-lg font-bold text-gray-900 flex items-center gap-2">
                       {ch.icon} {ch.label} Logic Flow
                    </h3>
                    <p className="text-sm text-gray-500 mt-1">{ch.description}</p>
                  </div>

                  {/* Flow Stages */}
                  <div className="relative">
                    <div className="absolute left-6 top-6 bottom-6 w-0.5 bg-gray-200"></div>
                    <div className="space-y-6 relative">
                      {ch.steps.map((step, idx) => (
                        <div key={idx} className="flex gap-4">
                          <div className="w-12 h-12 rounded-full border-4 border-gray-50 bg-white shadow-sm flex items-center justify-center font-bold text-emerald-600 shrink-0 z-10 text-sm">
                            {idx + 1}
                          </div>
                          <div className="bg-white border border-gray-100 rounded-xl p-4 shadow-sm flex-1">
                            <h4 className="font-bold text-gray-900 text-sm mb-1">{step.title}</h4>
                            <p className="text-sm text-gray-500 leading-relaxed">{step.desc}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Invariants */}
                  <div className="mt-8 pt-6 border-t border-gray-200 border-dashed">
                    <h3 className="text-xs font-bold tracking-widest text-gray-400 mb-4 uppercase">Strict Channel Invariants</h3>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      {ch.invariants.map((inv, idx) => (
                        <div key={idx} className="bg-gray-100/50 rounded-xl p-4 border border-gray-100">
                          <h4 className="font-bold text-sm text-gray-900 flex items-center gap-2 mb-1.5">
                            {inv.icon} {inv.title}
                          </h4>
                          <p className="text-xs text-gray-500">{inv.desc}</p>
                        </div>
                      ))}
                    </div>
                  </div>

                </TabsContent>
              ))}
            </div>
            
          </Tabs>
        </div>

      </DialogContent>
    </Dialog>
  );
}
