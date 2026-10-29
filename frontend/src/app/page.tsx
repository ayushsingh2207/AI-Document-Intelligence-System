"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Navbar } from "@/components/Navbar";
import { MetricsCards } from "@/components/MetricsCards";
import { FileUpload } from "@/components/FileUpload";
import { DocumentViewer } from "@/components/DocumentViewer";
import { SearchInterface } from "@/components/SearchInterface";
import { ContractInterface } from "@/components/ContractInterface";
import {
  checkBackendHealth,
  HealthResponse,
  DocumentExtractionResponse,
  getIndexStats,
  IndexStatsResponse,
  listIndexedDocuments,
  getDocumentChunks,
  DocumentSummary,
  Citation,
} from "@/lib/api";
import {
  Sparkles,
  Layers,
  ShieldCheck,
  Clock,
  ArrowRight,
  Search,
  FileText,
  BookmarkCheck,
  CheckCircle2,
  Scale,
} from "lucide-react";

export default function Home() {
  const [backendHealth, setBackendHealth] = useState<HealthResponse | null>(null);
  const [healthLoading, setHealthLoading] = useState<boolean>(true);
  const [activeDocument, setActiveDocument] = useState<DocumentExtractionResponse | null>(null);
  const [targetPageNumber, setTargetPageNumber] = useState<number | undefined>(undefined);
  const [activeCitation, setActiveCitation] = useState<Citation | null>(null);
  const [sessionDocuments, setSessionDocuments] = useState<DocumentExtractionResponse[]>([]);
  const [indexedDocs, setIndexedDocs] = useState<DocumentSummary[]>([]);
  const [activeTab, setActiveTab] = useState<"ingestion" | "search" | "contract">("ingestion");
  const [indexStats, setIndexStats] = useState<IndexStatsResponse | null>(null);
  const [refreshTrigger, setRefreshTrigger] = useState<number>(0);
  const [showDiagnostics, setShowDiagnostics] = useState<boolean>(false);

  // Fetch backend health, index stats, and restore indexed documents
  const fetchHealthAndStats = useCallback(async () => {
    setHealthLoading(true);
    try {
      const [health, stats, indexedDocs] = await Promise.all([
        checkBackendHealth().catch(() => null),
        getIndexStats().catch(() => null),
        listIndexedDocuments().catch(() => []),
      ]);
      setBackendHealth(health);
      setIndexStats(stats);
      setIndexedDocs(indexedDocs || []);

      // Restore indexed document metadata so document list survives browser refresh
      if (indexedDocs && indexedDocs.length > 0) {
        setSessionDocuments((prevDocs) => {
          const existingIds = new Set(prevDocs.map((d) => d.doc_id));
          const restoredDocs: DocumentExtractionResponse[] = indexedDocs
            .filter((idoc) => !existingIds.has(idoc.doc_id))
            .map((idoc) => ({
              success: true,
              doc_id: idoc.doc_id,
              filename: idoc.filename,
              file_type: idoc.file_type,
              file_size_bytes: 0,
              file_size_formatted: `${idoc.total_chunks} passages`,
              total_pages: Math.max(1, idoc.total_pages),
              total_chunks: idoc.total_chunks,
              total_characters: 0,
              total_words: 0,
              preview_text: "",
              extracted_pages: Array.from({ length: Math.max(1, idoc.total_pages) }, (_, idx) => ({
                page_number: idx + 1,
                text: "",
                char_count: 0,
                word_count: 0,
                is_approximate: false,
                boundary_type: "persisted_index",
              })),
              metadata: {
                processed_at: idoc.indexed_at || idoc.updated_at || idoc.created_at,
                restored_from_index: true,
              },
              message: "Restored from persistent knowledge base.",
            }));
          return [...prevDocs, ...restoredDocs];
        });
      }
    } catch {
      setBackendHealth(null);
    } finally {
      setHealthLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchHealthAndStats();
  }, [fetchHealthAndStats, refreshTrigger]);

  // Populate chunk text for restored documents on-demand
  const ensureDocumentPages = async (doc: DocumentExtractionResponse): Promise<DocumentExtractionResponse> => {
    const hasText = doc.extracted_pages.some((p) => p.text && p.text.trim().length > 0);
    if (hasText || !doc.doc_id) {
      return doc;
    }

    try {
      const chunks = await getDocumentChunks(doc.doc_id);
      if (chunks && chunks.length > 0) {
        const pageMap = new Map<number, string[]>();
        for (const chunk of chunks) {
          const pNum = chunk.page_number || 1;
          if (!pageMap.has(pNum)) {
            pageMap.set(pNum, []);
          }
          pageMap.get(pNum)!.push(chunk.text);
        }

        const updatedPages = doc.extracted_pages.map((p) => {
          const texts = pageMap.get(p.page_number) || [];
          const fullText = texts.join("\n\n");
          return {
            ...p,
            text: fullText,
            char_count: fullText.length,
            word_count: fullText.split(/\s+/).filter(Boolean).length,
          };
        });

        const updatedDoc = {
          ...doc,
          extracted_pages: updatedPages,
          total_words: updatedPages.reduce((acc, p) => acc + p.word_count, 0),
          total_characters: updatedPages.reduce((acc, p) => acc + p.char_count, 0),
        };

        setSessionDocuments((prev) =>
          prev.map((d) => (d.doc_id === doc.doc_id ? updatedDoc : d))
        );
        return updatedDoc;
      }
    } catch {
      // Non-fatal fallback
    }
    return doc;
  };

  const handleUploadSuccess = (doc: DocumentExtractionResponse) => {
    setActiveDocument(doc);
    setTargetPageNumber(1);
    setActiveCitation(null);
    setSessionDocuments((prev) => [doc, ...prev.filter((d) => d.filename !== doc.filename)]);
    setRefreshTrigger((prev) => prev + 1);
  };

  const handleClearActiveDocument = () => {
    setActiveDocument(null);
    setTargetPageNumber(undefined);
    setActiveCitation(null);
  };

  const handleSelectDocumentPage = async (docId: string, pageNumber: number) => {
    setActiveCitation(null);
    const foundDoc = sessionDocuments.find((d) => d.doc_id === docId);
    if (foundDoc) {
      const populatedDoc = await ensureDocumentPages(foundDoc);
      setActiveDocument(populatedDoc);
    }
    setTargetPageNumber(pageNumber);
    setActiveTab("ingestion");
  };

  const handleSelectCitation = async (citation: Citation) => {
    setActiveCitation(citation);
    const foundDoc = sessionDocuments.find((d) => d.doc_id === citation.doc_id);
    if (foundDoc) {
      const populatedDoc = await ensureDocumentPages(foundDoc);
      setActiveDocument(populatedDoc);
    }
    setTargetPageNumber(citation.page_number);
    setActiveTab("ingestion");
  };

  // Aggregated session statistics
  const totalDocuments = sessionDocuments.length;
  const totalPages = sessionDocuments.reduce((acc, d) => acc + d.total_pages, 0);
  const totalWords = sessionDocuments.reduce((acc, d) => acc + d.total_words, 0);
  const maxSizeMb = backendHealth?.max_upload_size_mb || 15;
  const isHealthy = backendHealth?.status === "healthy";
  const isDemoMode = backendHealth?.demo_mode || process.env.NEXT_PUBLIC_DEMO_MODE === "true";

  return (
    <div className="min-h-screen bg-slate-950 bg-grid-pattern relative flex flex-col">
      {/* Ambient background glows */}
      <div className="absolute top-0 left-1/4 w-96 h-96 bg-cyan-600/10 rounded-full blur-3xl pointer-events-none animate-pulse-glow" />
      <div className="absolute top-40 right-1/4 w-96 h-96 bg-indigo-600/10 rounded-full blur-3xl pointer-events-none" />

      {/* Navigation */}
      <Navbar
        backendHealth={backendHealth}
        healthLoading={healthLoading}
        onRefreshHealth={fetchHealthAndStats}
        showDiagnostics={showDiagnostics}
        onToggleDiagnostics={() => setShowDiagnostics(!showDiagnostics)}
      />

      {/* Main Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 md:py-12 space-y-8 relative z-10">
        {/* Public Demo Mode Disclaimer */}
        {isDemoMode && (
          <div className="bg-amber-950/40 border border-amber-500/40 text-amber-200 px-4 py-3 rounded-xl flex items-center justify-between text-xs sm:text-sm shadow-lg shadow-amber-950/20">
            <div className="flex items-center gap-3">
              <span className="text-lg">⚠️</span>
              <div>
                <p className="font-semibold text-amber-100">
                  Academic demonstration. Do not upload confidential or personal information.
                </p>
                <p className="text-xs text-amber-300/80 mt-0.5">
                  Public demo mode active: Uploads and document deletions are disabled to safeguard system integrity. You can freely search, ask grounded questions, inspect verifiable citations, and evaluate CUAD clauses across the pre-loaded academic demo corpus.
                </p>
              </div>
            </div>
            <span className="hidden sm:inline-block px-2.5 py-1 rounded-md text-xs font-mono font-medium bg-amber-500/20 text-amber-300 border border-amber-500/30 uppercase tracking-wider">
              Demo Mode
            </span>
          </div>
        )}

        {/* User-Focused Hero Section */}
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 pb-2">
          <div className="space-y-3">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-indigo-950/80 border border-indigo-800/80 text-indigo-300">
              <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
              <span>Document Processing &amp; Semantic Retrieval System</span>
            </div>
            <h1 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold text-white tracking-tight leading-tight">
              AI Document <span className="bg-gradient-to-r from-cyan-400 via-indigo-400 to-purple-400 bg-clip-text text-transparent">Intelligence</span>
            </h1>
            <p className="text-sm sm:text-base text-slate-400 max-w-2xl leading-relaxed">
              Upload documents, extract text with verified page boundaries, and perform instant natural language search across passages with exact page citations.
            </p>
          </div>

          {/* User-Centric Value Highlights */}
          <div className="hidden lg:flex flex-col items-end gap-2 text-xs text-slate-400">
            <div className="flex items-center gap-2 bg-slate-900/60 border border-slate-800 px-3 py-1.5 rounded-xl">
              <BookmarkCheck className="w-3.5 h-3.5 text-indigo-400" />
              <span>Verified Page &amp; Character Citations</span>
            </div>
            <div className="flex items-center gap-2 bg-slate-900/60 border border-slate-800 px-3 py-1.5 rounded-xl">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
              <span>Self-Hosted Backend Inference (Local CPU in Dev) • No 3rd-Party AI APIs</span>
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

        {/* Tab Switcher: Ingestion & Reader vs Semantic Search */}
        <div className="flex items-center justify-between border-b border-slate-800/80 pb-4">
          <div className="flex items-center gap-2 bg-slate-900/80 p-1.5 rounded-2xl border border-slate-800/80 backdrop-blur-md">
            <button
              onClick={() => setActiveTab("ingestion")}
              id="tab-btn-ingestion"
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs sm:text-sm font-semibold transition-all cursor-pointer ${
                activeTab === "ingestion"
                  ? "bg-gradient-to-r from-cyan-500 to-blue-600 text-white shadow-lg shadow-cyan-500/20"
                  : "text-slate-400 hover:text-white hover:bg-slate-800/60"
              }`}
            >
              <FileText className="w-4 h-4" />
              <span>Ingestion &amp; Document Reader</span>
              {sessionDocuments.length > 0 && (
                <span className="ml-1 px-1.5 py-0.5 rounded-full text-[10px] bg-cyan-950 text-cyan-300 border border-cyan-800">
                  {sessionDocuments.length}
                </span>
              )}
            </button>

            <button
              onClick={() => setActiveTab("search")}
              id="tab-btn-search"
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs sm:text-sm font-semibold transition-all cursor-pointer ${
                activeTab === "search"
                  ? "bg-gradient-to-r from-indigo-500 to-purple-600 text-white shadow-lg shadow-indigo-500/20"
                  : "text-slate-400 hover:text-white hover:bg-slate-800/60"
              }`}
            >
              <Search className="w-4 h-4" />
              <span>Semantic Search &amp; Citations</span>
              {indexStats && indexStats.total_vectors > 0 && (
                <span className="ml-1 px-1.5 py-0.5 rounded-full text-[10px] bg-indigo-950 text-indigo-300 border border-indigo-800 font-mono">
                  {indexStats.total_vectors} passages
                </span>
              )}
            </button>

            <button
              onClick={() => setActiveTab("contract")}
              id="tab-btn-contract"
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs sm:text-sm font-semibold transition-all cursor-pointer ${
                activeTab === "contract"
                  ? "bg-gradient-to-r from-amber-500 to-indigo-600 text-white shadow-lg shadow-amber-500/20"
                  : "text-slate-400 hover:text-white hover:bg-slate-800/60"
              }`}
            >
              <Scale className="w-4 h-4" />
              <span>Contract Intelligence</span>
              <span className="ml-1 px-1.5 py-0.5 rounded-full text-[10px] bg-amber-950 text-amber-300 border border-amber-800 font-mono">
                CUAD 41
              </span>
            </button>
          </div>

          {/* Genuine Dynamic Status Pill - Reflects actual backend connection */}
          <div className="hidden sm:flex items-center gap-2 text-xs">
            {isHealthy ? (
              <span className="flex items-center gap-1.5 text-emerald-400">
                <span className="w-2 h-2 rounded-full bg-emerald-400" />
                <span>Search Engine Active</span>
              </span>
            ) : (
              <span className="flex items-center gap-1.5 text-rose-400">
                <span className="w-2 h-2 rounded-full bg-rose-400" />
                <span>Backend Offline</span>
              </span>
            )}
          </div>
        </div>

        {/* Tab 1: Ingestion & Document Reader */}
        {activeTab === "ingestion" && (
          <div className="space-y-6">
            {!activeDocument ? (
              <div className="space-y-6">
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-lg font-bold text-white tracking-tight">
                      Document Ingestion Portal
                    </h2>
                    <p className="text-xs text-slate-400">
                      Upload a PDF, DOCX, or TXT file to extract text, segment passages, and make contents instantly searchable.
                    </p>
                  </div>
                </div>

                <FileUpload
                  onUploadSuccess={handleUploadSuccess}
                  maxSizeMb={maxSizeMb}
                  isDemoMode={isDemoMode}
                />
              </div>
            ) : (
              <DocumentViewer
                document={activeDocument}
                onClear={handleClearActiveDocument}
                initialPageNumber={targetPageNumber}
                activeCitation={activeCitation}
                onClearCitation={() => setActiveCitation(null)}
              />
            )}

            {/* Restored / Recent Uploads in Knowledge Base */}
            {sessionDocuments.length > 0 && !activeDocument && (
              <div className="rounded-3xl bg-slate-900/50 border border-slate-800/80 p-6">
                <h3 className="text-sm font-bold text-white flex items-center gap-2 mb-4">
                  <Clock className="w-4 h-4 text-cyan-400" />
                  <span>Indexed Documents in Knowledge Base ({sessionDocuments.length})</span>
                </h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                  {sessionDocuments.map((doc, idx) => (
                    <div
                      key={idx}
                      onClick={async () => {
                        const populated = await ensureDocumentPages(doc);
                        setActiveDocument(populated);
                        setTargetPageNumber(1);
                        setActiveCitation(null);
                      }}
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
                        <span>
                          {doc.total_pages} page(s) • {doc.total_chunks || 0} passages
                        </span>
                        <ArrowRight className="w-3.5 h-3.5 text-slate-500 group-hover:text-cyan-400 transition-colors" />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Tab 2: Semantic Search & Vector Citations */}
        {activeTab === "search" && (
          <div className="space-y-6">
            <SearchInterface
              onSelectDocumentPage={handleSelectDocumentPage}
              onSelectCitation={handleSelectCitation}
              refreshTrigger={refreshTrigger}
              showDiagnostics={showDiagnostics}
              isDemoMode={isDemoMode}
            />
          </div>
        )}

        {/* Tab 3: Legal Contract Intelligence (CUAD 41 Categories) */}
        {activeTab === "contract" && (
          <div className="space-y-6">
            <ContractInterface
              indexedDocs={indexedDocs}
              onSelectCitation={handleSelectCitation}
              onSelectDocumentPage={handleSelectDocumentPage}
            />
          </div>
        )}

        {/* System Capabilities & Roadmap (Clean distinction between active and planned features) */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 pt-4">
          {/* Active Capabilities */}
          <div className="rounded-3xl bg-slate-900/40 border border-slate-800/80 p-6 space-y-4">
            <div className="flex items-center gap-2.5">
              <div className="p-2 rounded-xl bg-emerald-950/60 border border-emerald-800/60 text-emerald-400">
                <CheckCircle2 className="w-4 h-4" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-white">
                  Active Capabilities (Phases 1 &amp; 2)
                </h3>
                <span className="text-[10px] text-emerald-400 font-medium">Fully Operational</span>
              </div>
            </div>
            <ul className="space-y-2.5 text-xs text-slate-400">
              <li className="flex items-start gap-2">
                <span className="text-emerald-400 mt-0.5">✓</span>
                <span><strong>Multi-Format Ingestion:</strong> Deep magic-byte validation for PDF, DOCX, and TXT with file-size protections.</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-emerald-400 mt-0.5">✓</span>
                <span><strong>Page Preservation:</strong> Preserves exact page demarcations for PDF/DOCX and clean character windows for TXT.</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-emerald-400 mt-0.5">✓</span>
                <span><strong>Semantic Chunking:</strong> Intelligent paragraph and sentence segmentation with configurable overlap.</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-emerald-400 mt-0.5">✓</span>
                <span><strong>Cosine Similarity Search:</strong> Exact vector similarity retrieval with ranked results and verified page citations.</span>
              </li>
            </ul>
          </div>

          {/* Planned Roadmap */}
          <div className="rounded-3xl bg-slate-900/40 border border-slate-800/80 p-6 space-y-4">
            <div className="flex items-center gap-2.5">
              <div className="p-2 rounded-xl bg-indigo-950/60 border border-indigo-800/60 text-indigo-400">
                <Layers className="w-4 h-4" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-white">
                  Planned Roadmap (Phase 3 &amp; Beyond)
                </h3>
                <span className="text-[10px] text-indigo-400 font-medium">Future Enhancements</span>
              </div>
            </div>
            <ul className="space-y-2.5 text-xs text-slate-400">
              <li className="flex items-start gap-2">
                <span className="text-indigo-400 mt-0.5">○</span>
                <span><strong>Cross-Document Synthesis:</strong> Comparative analysis and multi-document theme aggregation.</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-indigo-400 mt-0.5">○</span>
                <span><strong>Key-Value &amp; Entity Extraction:</strong> Automated extraction of contract clauses, names, dates, and amounts.</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-indigo-400 mt-0.5">○</span>
                <span><strong>Generative QA Grounding:</strong> Natural language answer generation strictly cited to retrieved source passages.</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-indigo-400 mt-0.5">○</span>
                <span><strong>Hybrid Search:</strong> BM25 keyword matching fused with dense vector embeddings for technical vocabulary.</span>
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
            <span className="text-cyan-400">Deployable on Vercel &amp; Render/Railway</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
