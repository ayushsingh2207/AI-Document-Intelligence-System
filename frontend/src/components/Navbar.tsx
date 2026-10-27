"use client";

import React from "react";
import { HealthResponse } from "@/lib/api";
import { ShieldCheck, Activity, RefreshCw, Cpu, ExternalLink } from "lucide-react";

interface NavbarProps {
  backendHealth: HealthResponse | null;
  healthLoading: boolean;
  onRefreshHealth: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  backendHealth,
  healthLoading,
  onRefreshHealth,
}) => {
  const isHealthy = backendHealth?.status === "healthy";
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  return (
    <header className="sticky top-0 z-50 w-full border-b border-slate-800/80 bg-slate-950/80 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Brand / Logo */}
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-cyan-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-cyan-500/20 ring-1 ring-white/20">
            <Cpu className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-lg tracking-tight bg-gradient-to-r from-white via-slate-100 to-slate-400 bg-clip-text text-transparent">
                AI Document Intelligence
              </span>
              <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-cyan-950/80 text-cyan-400 border border-cyan-800/60">
                Phase 1
              </span>
            </div>
            <p className="text-xs text-slate-400 hidden sm:block">
              Ingestion, Validation & Page-Preserved Extraction Engine
            </p>
          </div>
        </div>

        {/* Right Controls */}
        <div className="flex items-center gap-3">
          {/* Backend Status Pill */}
          <div
            className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium border transition-all ${
              healthLoading
                ? "bg-slate-900 border-slate-800 text-slate-400"
                : isHealthy
                ? "bg-emerald-950/60 border-emerald-800/60 text-emerald-300"
                : "bg-rose-950/60 border-rose-800/60 text-rose-300"
            }`}
          >
            <span className="relative flex h-2 w-2">
              <span
                className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${
                  healthLoading
                    ? "bg-slate-400"
                    : isHealthy
                    ? "bg-emerald-400"
                    : "bg-rose-400"
                }`}
              />
              <span
                className={`relative inline-flex rounded-full h-2 w-2 ${
                  healthLoading
                    ? "bg-slate-500"
                    : isHealthy
                    ? "bg-emerald-500"
                    : "bg-rose-500"
                }`}
              />
            </span>
            <span className="hidden sm:inline">
              {healthLoading
                ? "Checking API..."
                : isHealthy
                ? `FastAPI Online (v${backendHealth?.version})`
                : "Backend Offline"}
            </span>
            <span className="sm:hidden">
              {isHealthy ? "Online" : "Offline"}
            </span>

            <button
              onClick={onRefreshHealth}
              disabled={healthLoading}
              title="Refresh backend status"
              className="p-0.5 hover:text-white transition-colors cursor-pointer disabled:opacity-50"
            >
              <RefreshCw className={`w-3 h-3 ${healthLoading ? "animate-spin" : ""}`} />
            </button>
          </div>

          {/* Swagger API Docs Link */}
          <a
            href={`${apiUrl}/docs`}
            target="_blank"
            rel="noopener noreferrer"
            className="hidden md:flex items-center gap-1 text-xs text-slate-400 hover:text-slate-200 px-3 py-1.5 rounded-lg border border-slate-800 hover:border-slate-700 bg-slate-900/50 transition-colors"
          >
            <span>FastAPI Docs</span>
            <ExternalLink className="w-3 h-3" />
          </a>

          {/* ₹0 Target Pill */}
          <div className="flex items-center gap-1.5 text-xs text-slate-400 bg-slate-900/80 px-2.5 py-1.5 rounded-lg border border-slate-800/80">
            <ShieldCheck className="w-3.5 h-3.5 text-indigo-400" />
            <span className="hidden lg:inline text-slate-300">₹0-Cost Open Stack</span>
          </div>
        </div>
      </div>
    </header>
  );
};
