"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { GitBranch, Globe, FileArchive, Box, ShieldCheck, Zap, Loader2 } from "lucide-react";

export function InitiateScanModal({ customTrigger }: { customTrigger?: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const router = useRouter();

  // API Integration state
  const [activeTab, setActiveTab] = useState("github");
  const [githubUrl, setGithubUrl] = useState("");
  const [githubPat, setGithubPat] = useState("");
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");
  const [successMsg, setSuccessMsg] = useState("");

  const handleDispatch = async () => {
    if (activeTab === "github") {
      if (!githubUrl) {
        setErrorMsg("GitHub Repository URL is required.");
        return;
      }

      setLoading(true);
      setErrorMsg("");
      setSuccessMsg("");

      try {
        const res = await fetch("http://localhost:8000/api/v1/scan/github", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            url: githubUrl,
            pat: githubPat || null,
            user_id: "c5f01e76-49b6-4234-9eac-dda501ca577c"
          })
        });

        const data = await res.json();

        if (!res.ok) {
          setErrorMsg(data.detail || "Failed to enqueue scan.");
        } else {
          setSuccessMsg("Scan successfully enqueued!");
          setTimeout(() => {
            setOpen(false);
            setSuccessMsg("");
            setGithubUrl("");
            setGithubPat("");
            // Redirect to scan page using job ID
            if (data.job_id) {
              router.push(`/scan/${data.job_id}`);
            }
          }, 1500);
        }
      } catch (e: any) {
        setErrorMsg(e.message || "Network error.");
      } finally {
        setLoading(false);
      }
    } else {
      setErrorMsg("Only GitHub channel is implemented in the backend currently.");
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      {customTrigger ? (
        <DialogTrigger className="w-full text-left bg-transparent border-none appearance-none cursor-pointer">
          {customTrigger}
        </DialogTrigger>
      ) : (
        <DialogTrigger className="inline-flex items-center justify-center text-sm rounded-lg bg-emerald-800 hover:bg-emerald-900 text-white px-6 h-9 font-medium shadow-sm transition-colors cursor-pointer">
          <Zap className="w-4 h-4 mr-2" />
          Start a scan
        </DialogTrigger>
      )}

      <DialogContent className="sm:max-w-3xl overflow-hidden p-0 rounded-2xl flex flex-col gap-0 border-gray-100 shadow-xl">

        <DialogHeader className="p-6 pb-4 border-b bg-gray-50/50">
          <DialogTitle className="text-xl font-bold font-sans">Initiate Security Scan</DialogTitle>
          <p className="text-sm text-gray-500 mt-1">Select an input channel to dispatch to the isolated worker queue</p>
        </DialogHeader>

        <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1 overflow-y-auto">

          <div className="px-6 pt-4">
            <TabsList className="w-full h-12 bg-gray-50/80 rounded-xl p-1 mb-6 flex space-x-1 outline outline-1 outline-gray-200">
              <TabsTrigger value="github" className="flex-1 rounded-lg data-[state=active]:bg-white data-[state=active]:shadow-sm">
                <GitBranch className="w-4 h-4 mr-2" /> GitHub
              </TabsTrigger>
              <TabsTrigger value="url" className="flex-1 rounded-lg data-[state=active]:bg-white data-[state=active]:shadow-sm">
                <Globe className="w-4 h-4 mr-2" /> Live URL
              </TabsTrigger>
              <TabsTrigger value="zip" className="flex-1 rounded-lg data-[state=active]:bg-white data-[state=active]:shadow-sm">
                <FileArchive className="w-4 h-4 mr-2" /> ZIP
              </TabsTrigger>
              <TabsTrigger value="docker" className="flex-1 rounded-lg data-[state=active]:bg-white data-[state=active]:shadow-sm">
                <Box className="w-4 h-4 mr-2" /> Docker
              </TabsTrigger>
            </TabsList>

            {errorMsg && <div className="mb-4 text-xs bg-rose-50 text-rose-600 px-4 py-2 rounded-lg border border-rose-100">{errorMsg}</div>}
            {successMsg && <div className="mb-4 text-xs bg-emerald-50 text-emerald-700 px-4 py-2 rounded-lg border border-emerald-100 font-medium">{successMsg}</div>}
          </div>

          <div className="px-6 pb-6 space-y-6">
            <TabsContent value="github" className="mt-0 space-y-4">
              <div className="space-y-2">
                <Label className="text-xs font-bold text-gray-700">GitHub Repository URL <span className="text-rose-500">*</span></Label>
                <Input value={githubUrl} onChange={(e) => setGithubUrl(e.target.value)} placeholder="https://github.com/owner/repository" className="h-11 rounded-lg bg-gray-50/50" />
              </div>

              <div className="space-y-2">
                <div className="flex justify-between">
                  <Label className="text-xs font-bold text-gray-700">Classic Personal Access Token (PAT)</Label>
                  <span className="text-xs font-mono text-gray-400">5-min ephemeral TTL</span>
                </div>
                <Input value={githubPat} onChange={(e) => setGithubPat(e.target.value)} type="password" placeholder="ghp_xxxxxxxxxxxxxxxxxxxx (Optional for public, required for private repos)" className="h-11 rounded-lg bg-gray-50/50" />
                <p className="text-[10px] text-gray-500">Only <strong className="font-semibold text-gray-700">Classic PAT</strong> with <code className="bg-gray-100 px-1 py-0.5 rounded text-gray-700">repo</code> (read-only) scope is accepted. Stored exclusively in RAM with a 5-minute TTL.</p>
              </div>

              <div className="space-y-2">
                <Label className="text-xs font-bold text-gray-700">Scan Label (Optional)</Label>
                <Input placeholder="e.g., First intake or Production Service" className="h-11 rounded-lg bg-gray-50/50" />
              </div>

              <div className="pt-2">
                <Label className="text-xs font-bold text-gray-500 mb-2 block">Quick Test Scenarios:</Label>
                <div className="grid grid-cols-2 gap-3">
                  <button onClick={() => setGithubUrl("https://github.com/vulnerable-ai/sample-chatbot")} className="text-left rounded-xl border p-4 bg-gray-50/30 hover:border-emerald-600 transition-colors">
                    <div className="font-bold text-sm text-gray-900 mb-1">Full AI Chatbot Audit</div>
                    <div className="text-xs text-gray-500">Public repo with prompt injection & leaked keys</div>
                  </button>
                  <button onClick={() => setGithubUrl("https://github.com/vulnerable-ai/missing-repo")} className="text-left rounded-xl border p-4 bg-gray-50/30 hover:border-emerald-600 transition-colors">
                    <div className="font-bold text-sm text-gray-900 mb-1">Test 404 Ambiguity Gate</div>
                    <div className="text-xs text-gray-500">Triggers synchronous edge rejection</div>
                  </button>
                </div>
              </div>
            </TabsContent>

            <TabsContent value="url" className="mt-0 space-y-4">
              <div className="text-sm text-gray-500 p-8 text-center bg-gray-50 rounded-xl border border-dashed">
                Live URL channel implementation is pending backend deployment.
              </div>
            </TabsContent>

            <TabsContent value="zip" className="mt-0 space-y-4">
              <div className="text-sm text-gray-500 p-8 text-center bg-gray-50 rounded-xl border border-dashed">
                ZIP Upload channel implementation is pending backend deployment.
              </div>
            </TabsContent>

            <TabsContent value="docker" className="mt-0 space-y-4">
              <div className="text-sm text-gray-500 p-8 text-center bg-gray-50 rounded-xl border border-dashed">
                Docker Image channel implementation is pending backend deployment.
              </div>
            </TabsContent>
          </div>
        </Tabs>

        {/* Footer Area */}
        <div className="p-4 px-6 border-t bg-white flex justify-between items-center rounded-b-2xl shrink-0">
          <div className="flex items-center text-xs font-mono text-gray-500">
            <ShieldCheck className="w-4 h-4 mr-2" /> Isolated Docker Sandbox
          </div>
          <div className="space-x-3">
            <Button variant="outline" className="rounded-lg text-sm bg-white" onClick={() => setOpen(false)} disabled={loading}>Cancel</Button>
            <Button onClick={handleDispatch} disabled={loading} className="bg-emerald-800 hover:bg-emerald-900 text-white rounded-lg px-6 font-semibold shadow-md inline-flex min-w-[170px] justify-center">
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : "Dispatch to Queue"}
            </Button>
          </div>
        </div>

      </DialogContent>
    </Dialog>
  );
}
