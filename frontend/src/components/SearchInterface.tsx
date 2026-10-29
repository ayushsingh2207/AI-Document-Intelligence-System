"use client";

import React, { useState, useEffect } from "react";
import {
  searchDocuments,
  SearchResult,
  SearchResponse,
  DocumentSummary,
  listIndexedDocuments,
  deleteIndexedDocument,
  getIndexStats,
  IndexStatsResponse,
  RetrievalStrategy,
  askQuestion,
  QARequest,
  QAResponse,
  Citation,
} from "@/lib/api";

interface SearchInterfaceProps {
  onSelectDocumentPage?: (docId: string, pageNumber: number) => void;
  onSelectCitation?: (citation: Citation) => void;
  refreshTrigger?: number;
  showDiagnostics?: boolean;
  isDemoMode?: boolean;
}

export const SearchInterface: React.FC<SearchInterfaceProps> = ({
  onSelectDocumentPage,
  onSelectCitation,
  refreshTrigger = 0,
  showDiagnostics = false,
  isDemoMode = false,
}) => {
  // Mode switcher: "qa" (Ask Questions) or "passages" (Passage Search)
  const [activeMode, setActiveMode] = useState<"qa" | "passages">("qa");

  // Passage search state
  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState(5);
  const [minScore, setMinScore] = useState(0.0);
  const [selectedDocId, setSelectedDocId] = useState<string>("");
  const [strategy, setStrategy] = useState<RetrievalStrategy>("hybrid");
  const [indexedDocs, setIndexedDocs] = useState<DocumentSummary[]>([]);
  const [indexStats, setIndexStats] = useState<IndexStatsResponse | null>(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<SearchResult[] | null>(null);
  const [searchMeta, setSearchMeta] = useState<{
    latencyMs: number;
    totalResults: number;
    modelName: string;
    retrievalStrategy: string;
    message: string;
  } | null>(null);

  // Q&A state
  const [qaQuestion, setQaQuestion] = useState("");
  const [qaDocScope, setQaDocScope] = useState<string>("");
  const [qaConfidenceThreshold, setQaConfidenceThreshold] = useState<number>(0.45);
  const [qaTopK, setQaTopK] = useState<number>(5);
  const [qaLoading, setQaLoading] = useState(false);
  const [qaError, setQaError] = useState<string | null>(null);
  const [qaResponse, setQaResponse] = useState<QAResponse | null>(null);
  const [showQaOptions, setShowQaOptions] = useState(false);

  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [showFilters, setShowFilters] = useState(false);
  const [showTechDetails, setShowTechDetails] = useState(showDiagnostics);

  // Sync tech details with external toggle if provided
  useEffect(() => {
    if (showDiagnostics !== undefined) {
      setShowTechDetails(showDiagnostics);
    }
  }, [showDiagnostics]);

  // Load documents and stats on mount and whenever refreshTrigger changes
  const loadIndexData = async () => {
    try {
      const [docs, stats] = await Promise.all([
        listIndexedDocuments().catch(() => []),
        getIndexStats().catch(() => null),
      ]);
      setIndexedDocs(docs);
      setIndexStats(stats);
    } catch {
      // Non-blocking if backend is spinning up
    }
  };

  useEffect(() => {
    loadIndexData();
  }, [refreshTrigger]);

  const handleSearch = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setError(null);

    try {
      const resp: SearchResponse = await searchDocuments(
        query.trim(),
        topK,
        selectedDocId ? selectedDocId : undefined,
        minScore,
        strategy
      );
      setResults(resp.results);
      setSearchMeta({
        latencyMs: resp.latency_ms ?? resp.search_time_ms ?? 0,
        totalResults: resp.total_results,
        modelName: resp.model_name ?? resp.model ?? "sentence-transformers/all-MiniLM-L6-v2",
        retrievalStrategy: resp.retrieval_strategy ?? strategy,
        message: resp.message ?? "",
      });
    } catch (err: any) {
      setError(err.message || "Failed to execute semantic search");
      setResults(null);
    } finally {
      setLoading(false);
    }
  };

  const handleAskQuestion = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!qaQuestion.trim()) return;

    setQaLoading(true);
    setQaError(null);

    try {
      const resp: QAResponse = await askQuestion({
        question: qaQuestion.trim(),
        doc_id: qaDocScope ? qaDocScope : null,
        top_k: qaTopK,
        confidence_threshold: qaConfidenceThreshold,
      });
      setQaResponse(resp);
    } catch (err: any) {
      setQaError(err.message || "Failed to execute question answering.");
      setQaResponse(null);
    } finally {
      setQaLoading(false);
    }
  };

  const handleCopyText = (chunkId: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(chunkId);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleDeleteDocument = async (docId: string, filename: string) => {
    if (isDemoMode) {
      alert("Document deletion is disabled in public demo mode.");
      return;
    }
    if (!confirm(`Are you sure you want to remove "${filename}" from the searchable knowledge base?`)) {
      return;
    }
    try {
      await deleteIndexedDocument(docId);
      if (selectedDocId === docId) setSelectedDocId("");
      await loadIndexData();
      if (results) {
        setResults((prev) => (prev ? prev.filter((r) => r.doc_id !== docId) : null));
      }
    } catch (err: any) {
      alert(`Deletion error: ${err.message}`);
    }
  };

  const getScoreBadge = (score: number) => {
    const percent = Math.round(score * 100);
    if (percent >= 80) {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
          {percent}% Match
        </span>
      );
    } else if (percent >= 60) {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/30">
          <span className="w-1.5 h-1.5 rounded-full bg-blue-400" />
          {percent}% Match
        </span>
      );
    } else if (percent >= 40) {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/30">
          <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
          {percent}% Match
        </span>
      );
    } else {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-zinc-800 text-zinc-400 border border-zinc-700">
          {percent}% Match
        </span>
      );
    }
  };

  const exampleQueries = [
    "Machine learning neural network architectures",
    "Confidentiality clause and liability limits",
    "Quarterly revenue and fiscal earnings",
    "Section headers and page breaks",
  ];

  const totalIndexedChunks = indexStats?.total_chunks ?? indexedDocs.reduce((acc, d) => acc + d.total_chunks, 0);

  return (
    <div className="space-y-6">
      {/* User-Focused Knowledge Base Status */}
      <div className="bg-gradient-to-r from-zinc-900/90 via-zinc-900/60 to-zinc-900/90 border border-zinc-800/80 rounded-2xl p-5 backdrop-blur-md shadow-xl">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 16l2.879-2.879m0 0a3 3 0 104.243-4.242 3 3 0 00-4.243 4.242zM21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-semibold text-zinc-100">Searchable Knowledge Base</h3>
                <span className={`px-2 py-0.5 text-[10px] font-medium tracking-wide uppercase rounded-md border ${
                  indexedDocs.length > 0
                    ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                    : "bg-zinc-800 text-zinc-400 border-zinc-700"
                }`}>
                  {indexedDocs.length > 0 ? "Ready for Search" : "No Documents Yet"}
                </span>
              </div>
              <p className="text-xs text-zinc-400 mt-0.5">
                Query across all indexed documents to retrieve verified source passages with page citations.
              </p>
            </div>
          </div>

          {/* Clean User-Facing Metrics */}
          <div className="flex items-center gap-3 text-xs">
            <div className="px-3 py-1.5 bg-zinc-800/50 rounded-lg border border-zinc-700/50">
              <span className="text-zinc-400">Documents: </span>
              <span className="font-bold text-zinc-200 font-mono ml-1">
                {indexedDocs.length}
              </span>
            </div>
            <div className="px-3 py-1.5 bg-zinc-800/50 rounded-lg border border-zinc-700/50">
              <span className="text-zinc-400">Indexed Passages: </span>
              <span className="font-bold text-indigo-400 font-mono ml-1">
                {totalIndexedChunks}
              </span>
            </div>
            <button
              onClick={loadIndexData}
              title="Refresh indexed document list"
              className="p-1.5 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 rounded-lg transition-colors cursor-pointer"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            </button>
          </div>
        </div>

        {/* Searchable Document Chips */}
        {indexedDocs.length > 0 ? (
          <div className="mt-4 pt-3 border-t border-zinc-800/80 flex flex-wrap items-center gap-2">
            <span className="text-[11px] font-medium text-zinc-400 mr-1">Active Documents:</span>
            {indexedDocs.map((doc) => (
              <div
                key={doc.doc_id}
                className="group flex items-center gap-1.5 px-2.5 py-1 bg-zinc-800/80 hover:bg-zinc-800 rounded-lg border border-zinc-700/60 text-xs text-zinc-300 transition-all"
              >
                <span className="w-1.5 h-1.5 rounded-full bg-indigo-400" />
                <span className="font-medium truncate max-w-[150px]" title={doc.filename}>
                  {doc.filename}
                </span>
                <span className="text-[10px] text-zinc-400 font-mono">
                  ({doc.total_pages}p • {doc.total_chunks} passages)
                </span>
                {!isDemoMode && (
                  <button
                    onClick={() => handleDeleteDocument(doc.doc_id, doc.filename)}
                    title={`Remove ${doc.filename} from index`}
                    className="opacity-0 group-hover:opacity-100 text-zinc-400 hover:text-rose-400 ml-1 transition-opacity cursor-pointer"
                  >
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div className="mt-3 pt-3 border-t border-zinc-800/60 text-xs text-zinc-500">
            Upload documents in the &quot;Ingestion &amp; Document Reader&quot; tab to make them searchable.
          </div>
        )}
      </div>

      {/* Mode Switcher Tabs */}
      <div className="flex items-center gap-2 border-b border-zinc-800 pb-3">
        <button
          type="button"
          id="mode-switch-qa"
          onClick={() => setActiveMode("qa")}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs sm:text-sm font-semibold transition-all cursor-pointer ${
            activeMode === "qa"
              ? "bg-gradient-to-r from-indigo-500 to-indigo-600 text-white shadow-lg shadow-indigo-500/25"
              : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/60"
          }`}
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
          </svg>
          <span>Ask Questions (Grounded Q&amp;A)</span>
        </button>

        <button
          type="button"
          id="mode-switch-passages"
          onClick={() => setActiveMode("passages")}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs sm:text-sm font-semibold transition-all cursor-pointer ${
            activeMode === "passages"
              ? "bg-gradient-to-r from-indigo-500 to-indigo-600 text-white shadow-lg shadow-indigo-500/25"
              : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/60"
          }`}
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <span>Passage Search (Hybrid / BM25 / Dense)</span>
        </button>
      </div>

      {/* Mode 1: Grounded Q&A Interface */}
      {activeMode === "qa" && (
        <div className="space-y-6">
          {/* Q&A Form */}
          <div className="bg-zinc-900/90 border border-zinc-800 rounded-2xl p-5 shadow-2xl backdrop-blur-md">
            <form onSubmit={handleAskQuestion} className="space-y-4">
              <div className="relative flex items-center">
                <div className="absolute left-4 text-indigo-400 pointer-events-none">
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
                <input
                  type="text"
                  id="qa-question-input"
                  value={qaQuestion}
                  onChange={(e) => setQaQuestion(e.target.value)}
                  placeholder="Ask a question grounded in your uploaded documents (e.g. 'What is the confidentiality duration?')..."
                  className="w-full pl-12 pr-32 py-3.5 bg-zinc-950/80 border border-zinc-800 rounded-xl text-zinc-100 placeholder-zinc-500 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500 transition-all shadow-inner"
                />
                <div className="absolute right-2 flex items-center gap-1.5">
                  {qaQuestion && (
                    <button
                      type="button"
                      onClick={() => setQaQuestion("")}
                      className="p-1.5 text-zinc-400 hover:text-zinc-200 rounded-lg hover:bg-zinc-800 transition-colors cursor-pointer"
                      title="Clear question"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  )}
                  <button
                    type="submit"
                    id="qa-submit-btn"
                    disabled={qaLoading || !qaQuestion.trim()}
                    className="px-4 py-2 bg-gradient-to-r from-indigo-500 to-indigo-600 hover:from-indigo-600 hover:to-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed text-white text-xs font-semibold rounded-lg shadow-lg shadow-indigo-500/20 transition-all flex items-center gap-2 cursor-pointer"
                  >
                    {qaLoading ? (
                      <>
                        <svg className="animate-spin w-3.5 h-3.5 text-white" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                        </svg>
                        <span>Answering...</span>
                      </>
                    ) : (
                      <span>Ask Question</span>
                    )}
                  </button>
                </div>
              </div>

              {/* Quick Example Suggestions */}
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-[11px] text-zinc-400 font-medium">Try asking:</span>
                {[
                  "What are the confidentiality obligations and duration?",
                  "What are the termination conditions and notice periods?",
                  "What is the liability limitation or indemnification cap?",
                  "What is the governing law and dispute resolution jurisdiction?",
                ].map((example, i) => (
                  <button
                    key={i}
                    type="button"
                    onClick={() => setQaQuestion(example)}
                    className="text-[11px] px-2.5 py-1 rounded-md bg-zinc-800/60 hover:bg-zinc-800 text-zinc-300 border border-zinc-700/40 hover:border-zinc-600 transition-colors cursor-pointer"
                  >
                    {example}
                  </button>
                ))}
              </div>

              {/* Controls Row: Document Scope and Options Toggle */}
              <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
                <div className="flex items-center gap-2">
                  <span className="text-[11px] text-zinc-400 font-medium">Scope:</span>
                  <select
                    id="qa-doc-scope-select"
                    value={qaDocScope}
                    onChange={(e) => setQaDocScope(e.target.value)}
                    className="px-3 py-1.5 bg-zinc-950/80 border border-zinc-800 rounded-lg text-xs text-zinc-200 focus:outline-none focus:border-indigo-500"
                  >
                    <option value="">All Indexed Documents ({indexedDocs.length})</option>
                    {indexedDocs.map((doc) => (
                      <option key={doc.doc_id} value={doc.doc_id}>
                        {doc.filename} ({doc.total_chunks} passages)
                      </option>
                    ))}
                  </select>
                </div>

                <button
                  type="button"
                  onClick={() => setShowQaOptions(!showQaOptions)}
                  className="text-[11px] text-indigo-400 hover:text-indigo-300 font-medium flex items-center gap-1 transition-colors cursor-pointer"
                >
                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" />
                  </svg>
                  <span>{showQaOptions ? "Hide Q&A Settings" : "Q&A Settings"}</span>
                </button>
              </div>

              {/* Q&A Settings Drawer */}
              {showQaOptions && (
                <div className="pt-4 border-t border-zinc-800 grid grid-cols-1 sm:grid-cols-2 gap-4 bg-zinc-950/40 p-4 rounded-xl border border-zinc-800/60">
                  <div>
                    <div className="flex justify-between text-xs font-medium text-zinc-300 mb-1.5">
                      <label>Confidence Threshold</label>
                      <span className="text-indigo-400 font-mono font-bold">
                        {(qaConfidenceThreshold * 100).toFixed(0)}%
                      </span>
                    </div>
                    <input
                      type="range"
                      min="0.10"
                      max="0.80"
                      step="0.05"
                      value={qaConfidenceThreshold}
                      onChange={(e) => setQaConfidenceThreshold(parseFloat(e.target.value))}
                      className="w-full accent-indigo-500 cursor-pointer"
                    />
                    <p className="text-[10px] text-zinc-500 mt-1">
                      Conservative cutoff below which the system abstains instead of guessing.
                    </p>
                  </div>

                  <div>
                    <div className="flex justify-between text-xs font-medium text-zinc-300 mb-1.5">
                      <label>Candidate Passages (top_k)</label>
                      <span className="text-indigo-400 font-mono font-bold">{qaTopK}</span>
                    </div>
                    <input
                      type="range"
                      min="1"
                      max="15"
                      value={qaTopK}
                      onChange={(e) => setQaTopK(parseInt(e.target.value, 10))}
                      className="w-full accent-indigo-500 cursor-pointer"
                    />
                    <p className="text-[10px] text-zinc-500 mt-1">
                      Number of hybrid retrieval chunks evaluated for sentence evidence.
                    </p>
                  </div>
                </div>
              )}
            </form>
          </div>

          {/* Q&A Error Banner */}
          {qaError && (
            <div className="p-4 bg-rose-500/10 border border-rose-500/30 rounded-xl flex items-start gap-3 text-rose-300 text-sm">
              <svg className="w-5 h-5 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <div>
                <p className="font-semibold">Question Answering Error</p>
                <p className="text-xs text-rose-400/90 mt-0.5">{qaError}</p>
              </div>
            </div>
          )}

          {/* Q&A Answered State */}
          {qaResponse && qaResponse.answered && (
            <div className="space-y-4" id="qa-answered-container">
              {/* Main Extractive Answer Card */}
              <div className="bg-gradient-to-br from-zinc-900/95 via-indigo-950/20 to-zinc-900/95 border border-indigo-500/40 rounded-2xl p-6 shadow-2xl backdrop-blur-md space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-800/80 pb-4">
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                    <h3 className="text-sm font-bold text-white tracking-wide">
                      Grounded Extractive Answer
                    </h3>
                  </div>

                  {/* Evidence Metrics & Guardrail Subtitle */}
                  <div className="flex flex-wrap items-center gap-3 text-xs">
                    <div className="px-3 py-1 bg-zinc-950/70 border border-zinc-800 rounded-lg flex items-center gap-2">
                      <span className="text-zinc-400">Evidence Score:</span>
                      <span className="font-mono font-bold text-indigo-300">
                        {(qaResponse.confidence * 100).toFixed(0)}%
                      </span>
                    </div>

                    <span className="px-2.5 py-1 rounded-lg bg-purple-500/10 text-purple-300 border border-purple-500/30 font-mono text-[11px]">
                      Strategy: {qaResponse.retrieval_strategy}
                    </span>

                    <span className="px-2.5 py-1 rounded-lg bg-zinc-800/80 text-zinc-400 border border-zinc-700/60 font-mono text-[11px]">
                      ⚡ {qaResponse.latency_ms.toFixed(1)} ms
                    </span>
                  </div>
                </div>

                {/* Answer Excerpt */}
                <div className="p-4 bg-zinc-950/80 border border-zinc-800/90 rounded-xl text-base sm:text-lg text-zinc-100 font-sans leading-relaxed selection:bg-indigo-500/30">
                  &ldquo;{qaResponse.answer}&rdquo;
                </div>

                <div className="text-[11px] text-zinc-500 italic">
                  * Note: Reported score is a heuristic evidence retrieval metric (cosine similarity + keyword overlap), not a calibrated statistical probability.
                </div>
              </div>

              {/* Source Citations */}
              <div className="space-y-3">
                <div className="flex items-center justify-between px-1">
                  <h4 className="text-xs font-bold text-zinc-300 uppercase tracking-wider flex items-center gap-2">
                    <svg className="w-4 h-4 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    <span>Supporting Source Evidence ({qaResponse.citations.length} citation{qaResponse.citations.length > 1 ? "s" : ""})</span>
                  </h4>
                  <span className="text-[11px] text-zinc-500">
                    Click a citation to navigate directly to the verified page excerpt
                  </span>
                </div>

                {qaResponse.citations.map((cit) => (
                  <div
                    key={cit.citation_id}
                    className="bg-zinc-900/90 hover:bg-zinc-900 border border-zinc-800/90 hover:border-zinc-700 rounded-2xl p-5 shadow-lg transition-all group"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
                      <div className="flex flex-wrap items-center gap-2">
                        {/* Citation ID Pill */}
                        <span className="px-2.5 py-0.5 rounded-lg bg-indigo-500/20 text-indigo-300 text-xs font-mono font-bold border border-indigo-500/40">
                          {cit.citation_id}
                        </span>

                        {/* Document Name */}
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-lg text-xs font-medium bg-zinc-800/80 text-zinc-300 border border-zinc-700/50">
                          <svg className="w-3.5 h-3.5 text-zinc-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                          </svg>
                          <span className="truncate max-w-[180px]" title={cit.filename}>
                            {cit.filename}
                          </span>
                        </span>

                        {/* Page Reference */}
                        <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-lg text-xs font-medium border ${
                          cit.is_approximate
                            ? "bg-amber-500/10 text-amber-300 border-amber-500/20"
                            : "bg-indigo-500/10 text-indigo-300 border-indigo-500/20"
                        }`}>
                          <span>Page {cit.page_number}</span>
                          <span className="text-[10px] opacity-75">
                            ({cit.is_approximate ? "Approximate Window" : "Exact Demarcation"})
                          </span>
                        </span>

                        {/* Character Offsets */}
                        <span className="text-[11px] text-zinc-400 font-mono px-2 py-0.5 bg-zinc-950/60 rounded border border-zinc-800">
                          Chars {cit.start_char}–{cit.end_char}
                        </span>

                        {/* Relevance Score */}
                        <span className="text-[11px] text-emerald-400 font-mono px-2 py-0.5 bg-emerald-500/10 rounded border border-emerald-500/30">
                          {(cit.relevance_score * 100).toFixed(0)}% Relevance
                        </span>
                      </div>

                      {/* Jump to Page & Citation */}
                      <button
                        onClick={() => {
                          if (onSelectCitation) {
                            onSelectCitation(cit);
                          } else if (onSelectDocumentPage) {
                            onSelectDocumentPage(cit.doc_id, cit.page_number);
                          }
                        }}
                        className="px-3 py-1.5 text-xs font-semibold text-white bg-gradient-to-r from-indigo-500 to-indigo-600 hover:from-indigo-600 hover:to-indigo-700 rounded-lg shadow-md transition-all flex items-center gap-1.5 cursor-pointer"
                      >
                        <span>Jump to Evidence (Page {cit.page_number})</span>
                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M14 5l7 7m0 0l-7 7m7-7H3" />
                        </svg>
                      </button>
                    </div>

                    {/* Exact Supporting Excerpt */}
                    <div className="mt-3 p-4 bg-zinc-950/70 border border-zinc-800/80 rounded-xl text-xs sm:text-sm text-zinc-300 leading-relaxed font-mono whitespace-pre-wrap select-text">
                      &ldquo;{cit.supporting_excerpt}&rdquo;
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Q&A Insufficient Evidence / Abstention State */}
          {qaResponse && !qaResponse.answered && (
            <div className="bg-amber-500/10 border border-amber-500/30 rounded-2xl p-6 shadow-xl space-y-4" id="qa-abstention-container">
              <div className="flex items-center justify-between gap-3 border-b border-amber-500/20 pb-3">
                <div className="flex items-center gap-2.5">
                  <div className="p-2 rounded-xl bg-amber-500/20 text-amber-400 border border-amber-500/40">
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                  </div>
                  <div>
                    <h4 className="text-sm font-bold text-amber-200">
                      Insufficient Evidence (Conservative Abstention)
                    </h4>
                    <span className="text-[10px] text-amber-400/80 font-mono">
                      Reason: {qaResponse.abstention_reason || "insufficient_evidence"} • Strategy: {qaResponse.retrieval_strategy} • {qaResponse.latency_ms.toFixed(1)}ms
                    </span>
                  </div>
                </div>

                <span className="text-xs font-mono font-semibold text-amber-400 px-2.5 py-1 bg-amber-500/20 border border-amber-500/30 rounded-lg">
                  Confidence: {(qaResponse.confidence * 100).toFixed(0)}%
                </span>
              </div>

              <div className="p-4 bg-zinc-950/70 border border-zinc-800 rounded-xl text-sm text-zinc-200 leading-relaxed">
                {qaResponse.answer}
              </div>

              <p className="text-xs text-zinc-400 leading-relaxed">
                Grounding Guardrail: Extractive question answering strictly enforces confidence thresholds and requires verifiable evidence in retrieved chunks. When retrieved evidence falls below the threshold ({(qaConfidenceThreshold * 100).toFixed(0)}%), the model refrains from generating ungrounded answers, and zero citations are fabricated.
              </p>
            </div>
          )}

          {/* Q&A Initial Prompt State */}
          {!qaResponse && !qaLoading && (
            <div className="text-center py-12 bg-zinc-900/30 border border-zinc-800/50 rounded-2xl p-6">
              <div className="w-12 h-12 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center mx-auto text-indigo-400 mb-3">
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <h4 className="text-sm font-semibold text-zinc-200">
                Grounded Question Answering Ready
              </h4>
              <p className="text-xs text-zinc-400 mt-1 max-w-md mx-auto">
                Ask questions across all indexed documents or scope to a single document. The grounded answering service uses hybrid retrieval, evaluates sentence-level evidence, and provides verifiable page citations with conservative abstention when evidence is lacking.
              </p>
            </div>
          )}
        </div>
      )}

      {/* Mode 2: Passage Search Interface (Preserving Hybrid, Dense, and BM25 modes) */}
      {activeMode === "passages" && (
        <div className="space-y-6">
          {/* Main Search Bar Form */}
          <div className="bg-zinc-900/90 border border-zinc-800 rounded-2xl p-5 shadow-2xl backdrop-blur-md">
            <form onSubmit={handleSearch} className="space-y-4">
              <div className="relative flex items-center">
                <div className="absolute left-4 text-zinc-400 pointer-events-none">
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                  </svg>
                </div>
                <input
                  type="text"
                  id="semantic-search-input"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search passages across documents (e.g. 'Confidentiality and liability limits')..."
                  className="w-full pl-12 pr-28 py-3.5 bg-zinc-950/80 border border-zinc-800 rounded-xl text-zinc-100 placeholder-zinc-500 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500 transition-all shadow-inner"
                />
                <div className="absolute right-2 flex items-center gap-1.5">
                  {query && (
                    <button
                      type="button"
                      onClick={() => setQuery("")}
                      className="p-1.5 text-zinc-400 hover:text-zinc-200 rounded-lg hover:bg-zinc-800 transition-colors cursor-pointer"
                      title="Clear query"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  )}
                  <button
                    type="submit"
                    id="semantic-search-submit-btn"
                    disabled={loading || !query.trim()}
                    className="px-4 py-2 bg-gradient-to-r from-indigo-500 to-indigo-600 hover:from-indigo-600 hover:to-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed text-white text-xs font-semibold rounded-lg shadow-lg shadow-indigo-500/20 transition-all flex items-center gap-2 cursor-pointer"
                  >
                    {loading ? (
                      <>
                        <svg className="animate-spin w-3.5 h-3.5 text-white" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                        </svg>
                        <span>Searching...</span>
                      </>
                    ) : (
                      <span>Search</span>
                    )}
                  </button>
                </div>
              </div>

              {/* Quick Example Suggestions */}
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-[11px] text-zinc-400 font-medium">Try searching:</span>
                {exampleQueries.map((example, i) => (
                  <button
                    key={i}
                    type="button"
                    onClick={() => setQuery(example)}
                    className="text-[11px] px-2.5 py-1 rounded-md bg-zinc-800/60 hover:bg-zinc-800 text-zinc-300 border border-zinc-700/40 hover:border-zinc-600 transition-colors cursor-pointer"
                  >
                    {example}
                  </button>
                ))}
              </div>

              {/* Retrieval Strategy Selector */}
              <div className="flex flex-wrap items-center gap-2 pt-2">
                <span className="text-[11px] text-zinc-400 font-medium mr-1">Retrieval:</span>
                <div className="flex items-center bg-zinc-950/60 border border-zinc-800/80 rounded-lg p-0.5">
                  {[
                    { key: "hybrid" as RetrievalStrategy, label: "Hybrid", desc: "Dense + BM25 (RRF)" },
                    { key: "dense" as RetrievalStrategy, label: "Dense", desc: "Semantic vectors only" },
                    { key: "bm25" as RetrievalStrategy, label: "BM25", desc: "Keyword matching only" },
                  ].map((opt) => (
                    <button
                      key={opt.key}
                      type="button"
                      onClick={() => setStrategy(opt.key)}
                      title={opt.desc}
                      className={`px-3 py-1.5 text-[11px] font-medium rounded-md transition-all cursor-pointer ${
                        strategy === opt.key
                          ? "bg-indigo-500/20 text-indigo-300 border border-indigo-500/40 shadow-sm"
                          : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50 border border-transparent"
                      }`}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
                <span className="text-[10px] text-zinc-500 ml-1">
                  {strategy === "hybrid"
                    ? "Combines semantic similarity with keyword matching via Reciprocal Rank Fusion"
                    : strategy === "dense"
                    ? "Searches using semantic vector similarity (all-MiniLM-L6-v2)"
                    : "Searches using BM25 lexical keyword matching"}
                </span>
                <button
                  type="button"
                  onClick={() => setShowFilters(!showFilters)}
                  className="ml-auto text-[11px] text-indigo-400 hover:text-indigo-300 font-medium flex items-center gap-1 transition-colors cursor-pointer"
                >
                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" />
                  </svg>
                  <span>{showFilters ? "Hide Search Options" : "Search Options"}</span>
                </button>
              </div>

              {/* Search Options Drawer */}
              {showFilters && (
                <div className="pt-4 border-t border-zinc-800 grid grid-cols-1 sm:grid-cols-3 gap-4 bg-zinc-950/40 p-4 rounded-xl border border-zinc-800/60">
                  <div>
                    <label className="block text-xs font-medium text-zinc-300 mb-1.5">
                      Filter by Document
                    </label>
                    <select
                      value={selectedDocId}
                      onChange={(e) => setSelectedDocId(e.target.value)}
                      className="w-full px-3 py-2 bg-zinc-900 border border-zinc-700 rounded-lg text-xs text-zinc-200 focus:outline-none focus:border-indigo-500"
                    >
                      <option value="">All Documents ({indexedDocs.length})</option>
                      {indexedDocs.map((doc) => (
                        <option key={doc.doc_id} value={doc.doc_id}>
                          {doc.filename} ({doc.total_chunks} passages)
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <div className="flex justify-between text-xs font-medium text-zinc-300 mb-1.5">
                      <label>Max Results</label>
                      <span className="text-indigo-400 font-mono font-bold">{topK}</span>
                    </div>
                    <input
                      type="range"
                      min="1"
                      max="20"
                      value={topK}
                      onChange={(e) => setTopK(parseInt(e.target.value, 10))}
                      className="w-full accent-indigo-500 cursor-pointer"
                    />
                  </div>

                  <div>
                    <div className="flex justify-between text-xs font-medium text-zinc-300 mb-1.5">
                      <label>Min Match Confidence</label>
                      <span className="text-indigo-400 font-mono font-bold">
                        {(minScore * 100).toFixed(0)}%
                      </span>
                    </div>
                    <input
                      type="range"
                      min="0"
                      max="0.8"
                      step="0.05"
                      value={minScore}
                      onChange={(e) => setMinScore(parseFloat(e.target.value))}
                      className="w-full accent-indigo-500 cursor-pointer"
                    />
                  </div>
                </div>
              )}
            </form>
          </div>

          {/* Error Banner */}
          {error && (
            <div className="p-4 bg-rose-500/10 border border-rose-500/30 rounded-xl flex items-start gap-3 text-rose-300 text-sm">
              <svg className="w-5 h-5 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <div>
                <p className="font-semibold">Search Request Failed</p>
                <p className="text-xs text-rose-400/90 mt-0.5">{error}</p>
              </div>
            </div>
          )}

          {/* Results Header */}
          {searchMeta && results && (
            <div className="flex flex-wrap items-center justify-between gap-3 px-1">
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-semibold text-zinc-200">
                  Retrieved Passages ({results.length})
                </h3>
                <span className="text-xs text-zinc-400">
                  for query &quot;<span className="text-indigo-300 font-medium">{query}</span>&quot;
                </span>
              </div>
              <div className="flex items-center gap-3 text-xs text-zinc-400">
                <span className="px-2 py-0.5 bg-zinc-800/80 rounded border border-zinc-700/60 font-mono">
                  ⚡ {(searchMeta.latencyMs ?? 0).toFixed(1)} ms
                </span>
                <span className={`px-2 py-0.5 rounded border font-mono ${
                  searchMeta.retrievalStrategy === "hybrid"
                    ? "bg-purple-500/10 text-purple-300 border-purple-500/30"
                    : searchMeta.retrievalStrategy === "bm25"
                    ? "bg-amber-500/10 text-amber-300 border-amber-500/30"
                    : "bg-indigo-500/10 text-indigo-300 border-indigo-500/30"
                }`}>
                  {searchMeta.retrievalStrategy === "hybrid"
                    ? "⚗ Hybrid (RRF)"
                    : searchMeta.retrievalStrategy === "bm25"
                    ? "🔤 BM25 Lexical"
                    : "🧠 Dense Semantic"}
                </span>
              </div>
            </div>
          )}

          {/* Results List */}
          {results && results.length > 0 && (
            <div className="space-y-4" id="semantic-search-results-list">
              {results.map((result, idx) => (
                <div
                  key={result.chunk_id}
                  className="bg-zinc-900/90 hover:bg-zinc-900 border border-zinc-800/90 hover:border-zinc-700 rounded-2xl p-5 shadow-lg transition-all group"
                >
                  <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="w-6 h-6 rounded-lg bg-zinc-800 text-zinc-300 text-xs font-mono font-bold flex items-center justify-center border border-zinc-700">
                        #{idx + 1}
                      </span>
                      {getScoreBadge(result.score)}

                      {/* Document Name Tag */}
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-lg text-xs font-medium bg-zinc-800/80 text-zinc-300 border border-zinc-700/50">
                        <svg className="w-3.5 h-3.5 text-zinc-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                        </svg>
                        <span className="truncate max-w-[180px]" title={result.filename}>
                          {result.filename}
                        </span>
                      </span>

                      {/* Page Reference Tag */}
                      <span
                        className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-lg text-xs font-medium border ${
                          result.is_approximate
                            ? "bg-amber-500/10 text-amber-300 border-amber-500/20"
                            : "bg-indigo-500/10 text-indigo-300 border-indigo-500/20"
                        }`}
                        title={
                          result.is_approximate
                            ? "Approximate page reference (TXT/unpaginated character window)"
                            : `Exact boundary: ${result.boundary_type}`
                        }
                      >
                        <span>Page {result.page_number}</span>
                        <span className="text-[10px] opacity-75">
                          ({result.is_approximate ? "Approximate Window" : "Exact Demarcation"})
                        </span>
                      </span>

                      {/* Character Offsets Tag */}
                      <span className="text-[11px] text-zinc-400 font-mono px-2 py-0.5 bg-zinc-950/60 rounded border border-zinc-800">
                        Chars {result.start_char}–{result.end_char} ({result.word_count} words)
                      </span>
                    </div>

                    {/* Actions: Jump to Page & Copy */}
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleCopyText(result.chunk_id, result.text)}
                        className="px-2.5 py-1 text-xs text-zinc-400 hover:text-zinc-200 bg-zinc-800/60 hover:bg-zinc-800 border border-zinc-700/40 rounded-lg transition-colors flex items-center gap-1.5 cursor-pointer"
                        title="Copy passage text"
                      >
                        {copiedId === result.chunk_id ? (
                          <>
                            <svg className="w-3.5 h-3.5 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                            </svg>
                            <span className="text-emerald-400 font-medium">Copied</span>
                          </>
                        ) : (
                          <>
                            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                            </svg>
                            <span>Copy</span>
                          </>
                        )}
                      </button>

                      {onSelectDocumentPage && (
                        <button
                          onClick={() => onSelectDocumentPage(result.doc_id, result.page_number)}
                          className="px-2.5 py-1 text-xs font-medium text-indigo-400 hover:text-indigo-300 bg-indigo-500/10 hover:bg-indigo-500/20 border border-indigo-500/30 rounded-lg transition-colors flex items-center gap-1 cursor-pointer"
                        >
                          <span>Jump to Page {result.page_number}</span>
                          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M14 5l7 7m0 0l-7 7m7-7H3" />
                          </svg>
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Chunk Content Text */}
                  <div className="mt-3 p-4 bg-zinc-950/70 border border-zinc-800/80 rounded-xl text-xs sm:text-sm text-zinc-300 leading-relaxed font-sans whitespace-pre-wrap select-text">
                    {result.text}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Empty State: No results for query */}
          {results && results.length === 0 && (
            <div className="text-center py-12 bg-zinc-900/40 border border-dashed border-zinc-800 rounded-2xl p-6">
              <div className="w-12 h-12 rounded-full bg-zinc-800 flex items-center justify-center mx-auto text-zinc-400 mb-3">
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <h4 className="text-sm font-semibold text-zinc-200">No matching passages found</h4>
              <p className="text-xs text-zinc-400 mt-1 max-w-sm mx-auto">
                Try adjusting your search terms or lowering the minimum match confidence slider in search options.
              </p>
            </div>
          )}

          {/* Initial State: Prompt to search */}
          {!results && !loading && (
            <div className="text-center py-12 bg-zinc-900/30 border border-zinc-800/50 rounded-2xl p-6">
              <div className="w-12 h-12 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center mx-auto text-indigo-400 mb-3">
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>
              <h4 className="text-sm font-semibold text-zinc-200">
                {strategy === "hybrid" ? "Hybrid Search Ready" : strategy === "bm25" ? "BM25 Lexical Search Ready" : "Dense Semantic Search Ready"}
              </h4>
              <p className="text-xs text-zinc-400 mt-1 max-w-md mx-auto">
                {strategy === "hybrid"
                  ? "Enter a query above. The hybrid engine combines semantic similarity (dense vectors) with lexical keyword matching (BM25) using Reciprocal Rank Fusion for comprehensive results."
                  : strategy === "bm25"
                  ? "Enter a query above. BM25 lexical search matches exact keywords and terms in your documents."
                  : "Enter a conceptual query or question above. The engine scans your processed documents and returns ranked passages with verified source-page references."}
              </p>
            </div>
          )}
        </div>
      )}

      {/* Collapsible Developer / Diagnostic Section (Cleanly separated from user view) */}
      <div className="pt-4 border-t border-zinc-800/80">
        <button
          type="button"
          onClick={() => setShowTechDetails(!showTechDetails)}
          className="flex items-center gap-2 text-xs text-zinc-400 hover:text-zinc-200 font-medium transition-colors cursor-pointer"
        >
          <svg className={`w-3.5 h-3.5 transition-transform ${showTechDetails ? "rotate-90" : ""}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7" />
          </svg>
          <span>{showTechDetails ? "Hide System Diagnostics & Architecture Info" : "View System Diagnostics & Model Information"}</span>
        </button>

        {showTechDetails && (
          <div className="mt-3 bg-zinc-950/80 border border-zinc-800/80 rounded-xl p-4 space-y-3 font-mono text-xs text-zinc-400">
            <div className="flex items-center justify-between pb-2 border-b border-zinc-800">
              <span className="font-semibold text-zinc-300">Internal Vector Store Diagnostics</span>
              <span className="text-[10px] px-2 py-0.5 rounded bg-zinc-800 text-zinc-400">FAISS IndexFlatIP</span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 text-[11px]">
              <div>
                <span className="text-zinc-500 block">Embedding Model:</span>
                <span className="text-zinc-300">{indexStats?.embedding_model || "all-MiniLM-L6-v2"}</span>
              </div>
              <div>
                <span className="text-zinc-500 block">Vector Dimensions:</span>
                <span className="text-zinc-300">{indexStats?.dimension || 384} dims (Unit-Normalized)</span>
              </div>
              <div>
                <span className="text-zinc-500 block">Indexed Vectors:</span>
                <span className="text-zinc-300">{indexStats?.total_vectors ?? 0}</span>
              </div>
              <div>
                <span className="text-zinc-500 block">Lexical Index:</span>
                <span className="text-zinc-300">BM25Okapi • rank_bm25 (MIT)</span>
              </div>
              <div>
                <span className="text-zinc-500 block">Fusion Method:</span>
                <span className="text-zinc-300">Reciprocal Rank Fusion (RRF, k=60)</span>
              </div>
              <div>
                <span className="text-zinc-500 block">License / Runtime:</span>
                <span className="text-zinc-300">Apache-2.0 / MIT • Self-Hosted CPU</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
