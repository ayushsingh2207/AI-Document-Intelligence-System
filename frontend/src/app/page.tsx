"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Navbar } from "@/components/Navbar";
import { MetricsCards } from "@/components/MetricsCards";
import { FileUpload } from "@/components/FileUpload";
import { DocumentViewer } from "@/components/DocumentViewer";
import { checkBackendHealth, HealthResponse, DocumentExtractionResponse } from "@/lib/api";
import {
  Sparkles,
  Layers,
  ShieldCheck,
  Zap,
  Clock,
  Terminal,
  ArrowRight,
} from "lucide-react";

export default function Home() {
  const [backendHealth, setBackendHealth] = useState<HealthResponse | null>(null);
  const [healthLoading, setHealthLoading] = useState<boolean>(true);
  const [activeDocument, setActiveDocument] = useState<DocumentExtractionResponse | null>(null);
  const [sessionDocuments, setSessionDocuments] = useState<DocumentExtractionResponse[]>([]);

  // Fetch backend health
  const fetchHealth = useCallback(async () => {
    setHealthLoading(true);
    try {
      const data = await checkBackendHealth();
      setBackendHealth(data);
    } catch {
      setBackendHealth(null);
    } finally {
      setHealthLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchHealth();
  }, [fetchHealth]);

  const handleUploadSuccess = (doc: DocumentExtractionResponse) => {
    setActiveDocument(doc);
    setSessionDocuments((prev) => [doc, ...prev]);
  };

  const handleClearActiveDocument = () => {
    setActiveDocument(null);
  };

  // Aggregated session statistics
  const totalDocuments = sessionDocuments.length;
  const totalPages = sessionDocuments.reduce((acc, d) => acc + d.total_pages, 0);
  const totalWords = sessionDocuments.reduce((acc, d) => acc + d.total_words, 0);
  const maxSizeMb = backendHealth?.max_upload_size_mb || 15;

  return (
    <div className="min-h-screen bg-slate-950 bg-grid-pattern relative flex flex-col">
      {/* Ambient background glows */}
      <div className="absolute top-0 left-1/4 w-96 h-96 bg-cyan-600/10 rounded-full blur-3xl pointer-events-none animate-pulse-glow" />
      <div className="absolute top-40 right-1/4 w-96 h-96 bg-indigo-600/10 rounded-full blur-3xl pointer-events-none" />

      {/* Navigation */}
      <Navbar
        backendHealth={backendHealth}
        healthLoading={healthLoading}
        onRefreshHealth={fetchHealth}
      />

      {/* Main Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 md:py-12 space-y-10 relative z-10">
        {/* Hero Section */}
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 pb-2">
          <div className="space-y-3">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-cyan-950/80 border border-cyan-800/80 text-cyan-300">
              <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
              <span>Phase 1 Initial Ingestion Engine</span>
            </div>
            <h1 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold text-white tracking-tight leading-tight">
              AI Document <span className="bg-gradient-to-r from-cyan-400 to-indigo-400 bg-clip-text text-transparent">Intelligence</span>
            </h1>
            <p className="text-sm sm:text-base text-slate-400 max-w-2xl leading-relaxed">
              Industrial document parsing pipeline for PDF, DOCX, and TXT files.
              Validates file signatures, enforces size constraints, and extracts
              clean text with preserved page demarcations.
            </p>
          </div>

          {/* Quick Architecture Pills */}
          <div className="hidden lg:flex flex-col items-end gap-2 text-xs text-slate-400">
            <div className="flex items-center gap-2 bg-slate-900/60 border border-slate-800 px-3 py-1.5 rounded-xl">
              <Zap className="w-3.5 h-3.5 text-amber-400" />
              <span>Zero-cost runtime • No paid API keys</span>
            </div>
            <div className="flex items-center gap-2 bg-slate-900/60 border border-slate-800 px-3 py-1.5 rounded-xl">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
              <span>Magic-byte validation & path sanitization</span>
            </div>
          </div>
        </div>

        {/* Real-time Session Metrics */}
        <MetricsCards
          documentsCount={totalDocuments}
          pagesCount={totalPages}
          wordsCount={totalWords}
          maxSizeMb={maxSizeMb}
        />

        {/* Document Ingestion & Viewer Area */}
        <div className="space-y-6">
          {!activeDocument ? (
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-bold text-white tracking-tight">
                    Document Ingestion Portal
                  </h2>
                  <p className="text-xs text-slate-400">
                    Upload a file or click one of the demo samples below to initiate extraction
                  </p>
                </div>
              </div>

              <FileUpload
                onUploadSuccess={handleUploadSuccess}
                maxSizeMb={maxSizeMb}
              />
            </div>
          ) : (
            <DocumentViewer
              document={activeDocument}
              onClear={handleClearActiveDocument}
            />
          )}
        </div>

        {/* Recent Session History (if documents were processed) */}
        {sessionDocuments.length > 1 && !activeDocument && (
          <div className="rounded-3xl bg-slate-900/50 border border-slate-800/80 p-6">
            <h3 className="text-sm font-bold text-white flex items-center gap-2 mb-4">
              <Clock className="w-4 h-4 text-cyan-400" />
              <span>Recent Uploads in this Session ({sessionDocuments.length})</span>
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {sessionDocuments.map((doc, idx) => (
                <div
                  key={idx}
                  onClick={() => setActiveDocument(doc)}
                  className="p-4 rounded-2xl bg-slate-950/60 border border-slate-800 hover:border-cyan-500/50 hover:bg-slate-900/80 transition-all cursor-pointer group"
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-semibold text-white truncate max-w-[180px]">
                      {doc.filename}
                    </span>
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-cyan-950 text-cyan-300 border border-cyan-800">
                      {doc.file_type}
                    </span>
                  </div>
                  <div className="text-[11px] text-slate-400 flex items-center justify-between">
                    <span>{doc.total_pages} page(s) • {doc.total_words} words</span>
                    <ArrowRight className="w-3.5 h-3.5 text-slate-500 group-hover:text-cyan-400 transition-colors" />
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Phase 1 Verification Checklist & Phase 2 Roadmap Box */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 pt-4">
          <div className="rounded-3xl bg-slate-900/40 border border-slate-800/80 p-6 space-y-4">
            <div className="flex items-center gap-2.5">
              <div className="p-2 rounded-xl bg-emerald-950/60 border border-emerald-800/60 text-emerald-400">
                <ShieldCheck className="w-4 h-4" />
              </div>
              <h3 className="text-sm font-bold text-white">
                Phase 1 Production Gates
              </h3>
            </div>
            <ul className="space-y-2 text-xs text-slate-400">
              <li className="flex items-center gap-2">
                <span className="text-emerald-400">✓</span>
                Next.js 16 + TypeScript + Tailwind CSS App Router UI
              </li>
              <li className="flex items-center gap-2">
                <span className="text-emerald-400">✓</span>
                FastAPI Python backend with clean modular router structure
              </li>
              <li className="flex items-center gap-2">
                <span className="text-emerald-400">✓</span>
                Strict PDF, DOCX, TXT validation with magic-byte checks
              </li>
              <li className="flex items-center gap-2">
                <span className="text-emerald-400">✓</span>
                Page reference preservation & aggregate token metrics
              </li>
              <li className="flex items-center gap-2">
                <span className="text-emerald-400">✓</span>
                Automated Pytest unit & integration suite passing
              </li>
            </ul>
          </div>

          <div className="rounded-3xl bg-slate-900/40 border border-slate-800/80 p-6 space-y-4">
            <div className="flex items-center gap-2.5">
              <div className="p-2 rounded-xl bg-cyan-950/60 border border-cyan-800/60 text-cyan-400">
                <Layers className="w-4 h-4" />
              </div>
              <h3 className="text-sm font-bold text-white">
                Next: Phase 2 Prerequisites
              </h3>
            </div>
            <ul className="space-y-2 text-xs text-slate-400">
              <li className="flex items-center gap-2">
                <span className="text-cyan-400">→</span>
                Sentence/semantic chunking strategies with overlap
              </li>
              <li className="flex items-center gap-2">
                <span className="text-cyan-400">→</span>
                Local ₹0 embeddings engine (e.g. fastembed / sentence-transformers)
              </li>
              <li className="flex items-center gap-2">
                <span className="text-cyan-400">→</span>
                Vector indexing (ChromaDB / Qdrant local embedded storage)
              </li>
              <li className="flex items-center gap-2">
                <span className="text-cyan-400">→</span>
                Semantic search & similarity retrieval over preserved pages
              </li>
            </ul>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="w-full border-t border-slate-800/60 bg-slate-950 py-6 mt-12 text-xs text-slate-500">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-4">
          <p>© 2026 AI Document Intelligence System. ₹0-Cost Architecture.</p>
          <div className="flex items-center gap-4">
            <span>FastAPI Backend: :8000</span>
            <span>•</span>
            <span>Next.js Frontend: :3000</span>
            <span>•</span>
            <span className="text-cyan-400">Deployable on Vercel & Render</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
