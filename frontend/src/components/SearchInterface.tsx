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
} from "@/lib/api";

interface SearchInterfaceProps {
  onSelectDocumentPage?: (docId: string, pageNumber: number) => void;
  refreshTrigger?: number;
}

export const SearchInterface: React.FC<SearchInterfaceProps> = ({
  onSelectDocumentPage,
  refreshTrigger = 0,
}) => {
  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState(5);
  const [minScore, setMinScore] = useState(0.0);
  const [selectedDocId, setSelectedDocId] = useState<string>("");
  const [indexedDocs, setIndexedDocs] = useState<DocumentSummary[]>([]);
  const [indexStats, setIndexStats] = useState<IndexStatsResponse | null>(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<SearchResult[] | null>(null);
  const [searchMeta, setSearchMeta] = useState<{
    latencyMs: number;
    totalResults: number;
    modelName: string;
  } | null>(null);

  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [showFilters, setShowFilters] = useState(false);

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
        minScore
      );
      setResults(resp.results);
      setSearchMeta({
        latencyMs: resp.latency_ms ?? resp.search_time_ms ?? 0,
        totalResults: resp.total_results,
        modelName: resp.model_name ?? resp.model ?? "sentence-transformers/all-MiniLM-L6-v2",
      });
    } catch (err: any) {
      setError(err.message || "Failed to execute semantic search");
      setResults(null);
    } finally {
      setLoading(false);
    }
  };

  const handleCopyText = (chunkId: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(chunkId);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleDeleteDocument = async (docId: string, filename: string) => {
    if (!confirm(`Are you sure you want to purge "${filename}" and its vector index embeddings?`)) {
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
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          {percent}% Cosine Match
        </span>
      );
    } else if (percent >= 60) {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/30">
          <span className="w-1.5 h-1.5 rounded-full bg-blue-400" />
          {percent}% Cosine Match
        </span>
      );
    } else if (percent >= 40) {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/30">
          <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
          {percent}% Cosine Match
        </span>
      );
    } else {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-zinc-800 text-zinc-400 border border-zinc-700">
          {percent}% Cosine Match
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

  return (
    <div className="space-y-6">
      {/* Index Status Bar */}
      <div className="bg-gradient-to-r from-zinc-900/90 via-zinc-900/60 to-zinc-900/90 border border-zinc-800/80 rounded-2xl p-4 sm:p-5 backdrop-blur-md shadow-xl">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
              </svg>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-semibold text-zinc-100">Local Vector Index (FAISS)</h3>
                <span className="px-2 py-0.5 text-[10px] font-medium tracking-wide uppercase rounded-md bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  Active
                </span>
              </div>
              <p className="text-xs text-zinc-400 mt-0.5">
                Model: <span className="text-zinc-300 font-mono">sentence-transformers/all-MiniLM-L6-v2</span> (384-d • Unit-Normalized Cosine Similarity)
              </p>
            </div>
          </div>

          {/* Quick Metrics */}
          <div className="flex items-center gap-4 text-xs">
            <div className="px-3 py-1.5 bg-zinc-800/50 rounded-lg border border-zinc-700/50">
              <span className="text-zinc-400">Indexed Vectors: </span>
              <span className="font-bold text-indigo-400 font-mono">
                {indexStats?.total_vectors ?? 0}
              </span>
            </div>
            <div className="px-3 py-1.5 bg-zinc-800/50 rounded-lg border border-zinc-700/50">
              <span className="text-zinc-400">Documents: </span>
              <span className="font-bold text-zinc-200 font-mono">
                {indexStats?.total_indexed_documents ?? indexedDocs.length}
              </span>
            </div>
            <button
              onClick={loadIndexData}
              title="Refresh Index Stats"
              className="p-1.5 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 rounded-lg transition-colors"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            </button>
          </div>
        </div>

        {/* Indexed Documents Badges / Deletion */}
        {indexedDocs.length > 0 && (
          <div className="mt-4 pt-3 border-t border-zinc-800/80 flex flex-wrap items-center gap-2">
            <span className="text-[11px] font-medium text-zinc-400 mr-1">Indexed Files:</span>
            {indexedDocs.map((doc) => (
              <div
                key={doc.doc_id}
                className="group flex items-center gap-1.5 px-2.5 py-1 bg-zinc-800/80 hover:bg-zinc-800 rounded-lg border border-zinc-700/60 text-xs text-zinc-300 transition-all"
              >
                <span className="w-1.5 h-1.5 rounded-full bg-indigo-400" />
                <span className="font-medium truncate max-w-[140px]" title={doc.filename}>
                  {doc.filename}
                </span>
                <span className="text-[10px] text-zinc-400 font-mono">
                  ({doc.total_chunks} chunks)
                </span>
                <button
                  onClick={() => handleDeleteDocument(doc.doc_id, doc.filename)}
                  title={`Purge ${doc.filename} from vector store`}
                  className="opacity-0 group-hover:opacity-100 text-zinc-400 hover:text-rose-400 ml-1 transition-opacity"
                >
                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

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
              placeholder="Ask a question or enter a semantic query (e.g. 'What are the termination clauses?')..."
              className="w-full pl-12 pr-28 py-3.5 bg-zinc-950/80 border border-zinc-800 rounded-xl text-zinc-100 placeholder-zinc-500 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500 transition-all shadow-inner"
            />
            <div className="absolute right-2 flex items-center gap-1.5">
              {query && (
                <button
                  type="button"
                  onClick={() => setQuery("")}
                  className="p-1.5 text-zinc-400 hover:text-zinc-200 rounded-lg hover:bg-zinc-800 transition-colors"
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
                className="px-4 py-2 bg-gradient-to-r from-indigo-500 to-indigo-600 hover:from-indigo-600 hover:to-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed text-white text-xs font-semibold rounded-lg shadow-lg shadow-indigo-500/20 transition-all flex items-center gap-2"
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
            <span className="text-[11px] text-zinc-400 font-medium">Try asking:</span>
            {exampleQueries.map((example, i) => (
              <button
                key={i}
                type="button"
                onClick={() => {
                  setQuery(example);
                }}
                className="text-[11px] px-2.5 py-1 rounded-md bg-zinc-800/60 hover:bg-zinc-800 text-zinc-300 border border-zinc-700/40 hover:border-zinc-600 transition-colors"
              >
                {example}
              </button>
            ))}
            <button
              type="button"
              onClick={() => setShowFilters(!showFilters)}
              className="ml-auto text-[11px] text-indigo-400 hover:text-indigo-300 font-medium flex items-center gap-1 transition-colors"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" />
              </svg>
              <span>{showFilters ? "Hide Search Options" : "Search Options"}</span>
            </button>
          </div>

          {/* Collapsible Search Options */}
          {showFilters && (
            <div className="pt-4 border-t border-zinc-800 grid grid-cols-1 sm:grid-cols-3 gap-4 bg-zinc-950/40 p-4 rounded-xl border">
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
                      {doc.filename} ({doc.total_chunks} chunks)
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <div className="flex justify-between text-xs font-medium text-zinc-300 mb-1.5">
                  <label>Top Results (K)</label>
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
                  <label>Min Similarity Threshold</label>
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
            <p className="font-semibold">Search Execution Error</p>
            <p className="text-xs text-rose-400/90 mt-0.5">{error}</p>
          </div>
        </div>
      )}

      {/* Search Results Summary Header */}
      {searchMeta && results && (
        <div className="flex flex-wrap items-center justify-between gap-3 px-1">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold text-zinc-200">
              Ranked Semantic Results ({results.length})
            </h3>
            <span className="text-xs text-zinc-400">
              for &quot;<span className="text-indigo-300 font-medium">{query}</span>&quot;
            </span>
          </div>
          <div className="flex items-center gap-3 text-xs text-zinc-400">
            <span className="px-2 py-0.5 bg-zinc-800/80 rounded border border-zinc-700/60 font-mono">
              ⚡ {(searchMeta?.latencyMs ?? 0).toFixed(1)} ms
            </span>
            <span className="px-2 py-0.5 bg-zinc-800/80 rounded border border-zinc-700/60 font-mono">
              Cosine Similarity (FAISS FlatIP)
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
                        ? "Approximate page reference (TXT/unpaginated stream window)"
                        : `Exact boundary: ${result.boundary_type}`
                    }
                  >
                    <span>Page {result.page_number}</span>
                    <span className="text-[10px] opacity-75">
                      ({result.is_approximate ? "Approx" : result.boundary_type})
                    </span>
                  </span>

                  {/* Character Offsets Tag */}
                  <span className="text-[11px] text-zinc-400 font-mono px-2 py-0.5 bg-zinc-950/60 rounded border border-zinc-800">
                    Chars {result.start_char}–{result.end_char} ({result.char_count} chars, {result.word_count} words)
                  </span>
                </div>

                {/* Actions: Jump to Page & Copy */}
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleCopyText(result.chunk_id, result.text)}
                    className="px-2.5 py-1 text-xs text-zinc-400 hover:text-zinc-200 bg-zinc-800/60 hover:bg-zinc-800 border border-zinc-700/40 rounded-lg transition-colors flex items-center gap-1.5"
                    title="Copy chunk text"
                  >
                    {copiedId === result.chunk_id ? (
                      <>
                        <svg className="w-3.5 h-3.5 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                        </svg>
                        <span className="text-emerald-400">Copied!</span>
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
                      className="px-2.5 py-1 text-xs font-medium text-indigo-400 hover:text-indigo-300 bg-indigo-500/10 hover:bg-indigo-500/20 border border-indigo-500/30 rounded-lg transition-colors flex items-center gap-1"
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
          <h4 className="text-sm font-semibold text-zinc-200">No matching semantic chunks found</h4>
          <p className="text-xs text-zinc-400 mt-1 max-w-sm mx-auto">
            Try lowering the minimum similarity threshold or using alternative phrasing for your query.
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
          <h4 className="text-sm font-semibold text-zinc-200">Semantic Search Ready</h4>
          <p className="text-xs text-zinc-400 mt-1 max-w-md mx-auto">
            Type any question, conceptual query, or keyword above to find semantically relevant passages across your indexed documents with exact page references.
          </p>
        </div>
      )}
    </div>
  );
};
