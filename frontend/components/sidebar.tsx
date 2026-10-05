import Link from "next/link";
import { Shield, LayoutDashboard, Search, Database, Fingerprint } from "lucide-react";
import { InitiateScanModal } from "@/components/initiate-scan-modal";
import { ArchitectureModal } from "@/components/architecture-modal";
import { TaxonomyModal } from "@/components/taxonomy-modal";

export function Sidebar() {
  return (
    <aside className="w-64 border-r bg-white/50 backdrop-blur-sm flex flex-col justify-between hidden md:flex shrink-0">
      <div className="p-6">
        <div className="flex items-center gap-3 mb-10 text-emerald-900">
          <Shield className="w-8 h-8 text-emerald-700" fill="currentColor" />
          <div className="font-bold leading-tight">
            <span className="block text-sm tracking-widest">SENTINFI</span>
            <span className="block text-xs font-semibold text-gray-500 tracking-wider">AI SECURITY</span>
          </div>
        </div>
        
        <div className="mb-4 text-xs font-bold text-gray-400 tracking-widest">WORKSPACE</div>
        <nav className="space-y-1">
          <Link href="/" className="flex items-center gap-3 px-3 py-2 bg-emerald-50 text-emerald-800 rounded-lg font-medium text-sm transition-colors cursor-pointer">
            <LayoutDashboard className="w-5 h-5 text-emerald-700" />
            Overview
          </Link>
          <InitiateScanModal customTrigger={
            <div className="flex items-center gap-3 px-3 py-2 text-gray-600 hover:bg-gray-100 rounded-lg font-medium text-sm transition-colors w-full text-left">
              <Search className="w-5 h-5" />
              New scan
              <span className="ml-auto text-xs text-gray-400 font-mono">+</span>
            </div>
          } />
          <ArchitectureModal customTrigger={
            <div className="flex items-center gap-3 px-3 py-2 text-gray-600 hover:bg-gray-100 rounded-lg font-medium text-sm transition-colors w-full text-left">
              <Database className="w-5 h-5" />
              Architecture
            </div>
          } />
          <TaxonomyModal customTrigger={
            <div className="flex items-center gap-3 px-3 py-2 text-gray-600 hover:bg-gray-100 rounded-lg font-medium text-sm transition-colors w-full text-left">
              <Fingerprint className="w-5 h-5" />
              AI Taxonomy
            </div>
          } />
        </nav>
      </div>

      <div className="p-6 border-t mt-auto">
        <div className="flex items-center gap-3 cursor-pointer group">
          <div className="w-8 h-8 rounded-full bg-emerald-800 text-white flex items-center justify-center font-semibold text-sm">
            AO
          </div>
          <div className="flex-1 overflow-hidden">
            <p className="text-sm font-semibold truncate group-hover:text-emerald-700 transition-colors">Alex Okafor</p>
            <p className="text-xs text-gray-500 truncate">security · production</p>
          </div>
        </div>
        <div className="mt-4 flex items-center gap-2 text-xs font-medium text-gray-600">
          <div className="w-2 h-2 rounded-full bg-emerald-500"></div>
          API connected
        </div>
      </div>
    </aside>
  );
}
