"use client";

import React, { useState } from "react";
import {
  DocumentSummary,
  analyzeContract,
  ContractAnalysisResponse,
  ClauseSpan,
  Citation,
} from "@/lib/api";
import {
  Scale,
  ShieldAlert,
  CheckCircle2,
  AlertCircle,
  FileText,
  Search,
  ArrowRight,
  Filter,
  Sparkles,
  Layers,
  ChevronRight,
  ChevronDown,
} from "lucide-react";

interface ContractInterfaceProps {
  indexedDocs: DocumentSummary[];
  onSelectCitation?: (citation: Citation) => void;
  onSelectDocumentPage?: (docId: string, pageNumber: number) => void;
}

// 6 intuitive legal domain groups for the 41 CUAD categories
const CATEGORY_GROUPS: Record<string, string[]> = {
  "Contract Identity & Parties": [
    "Document Name",
    "Parties",
    "Agreement Date",
    "Effective Date",
    "Expiration Date",
  ],
  "Term & Renewal": [
    "Renewal Term",
    "Notice Period To Terminate Renewal",
    "Termination For Convenience",
    "Post-Termination Services",
  ],
  "Restraints & Exclusivity": [
    "Non-Compete",
    "Exclusivity",
    "No-Solicit Of Customers",
    "No-Solicit Of Employees",
    "Non-Disparagement",
    "Competitive Restriction Exception",
  ],
  "Intellectual Property & Licensing": [
    "License Grant",
    "Non-Transferable License",
    "Irrevocable Or Perpetual License",
    "Unlimited/All-You-Can-Eat-License",
    "Affiliate License-Licensor",
    "Affiliate License-Licensee",
    "Ip Ownership Assignment",
    "Joint Ip Ownership",
    "Source Code Escrow",
  ],
  "Liability, Risk & Insurance": [
    "Cap On Liability",
    "Uncapped Liability",
    "Liquidated Damages",
    "Warranty Duration",
    "Insurance",
    "Covenant Not To Sue",
    "Third Party Beneficiary",
  ],
  "Commercial Terms & Governance": [
    "Governing Law",
    "Rofr/Rofo/Rofn",
    "Change Of Control",
    "Anti-Assignment",
    "Most Favored Nation",
    "Revenue/Profit Sharing",
    "Price Restrictions",
    "Minimum Commitment",
    "Volume Restriction",
    "Audit Rights",
  ],
};

export const ContractInterface: React.FC<ContractInterfaceProps> = ({
  indexedDocs,
  onSelectCitation,
  onSelectDocumentPage,
}) => {
  const [selectedDocId, setSelectedDocId] = useState<string>(
    indexedDocs.length > 0 ? indexedDocs[0].doc_id : ""
  );
  const [confidenceThreshold, setConfidenceThreshold] = useState<number>(3.0);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<ContractAnalysisResponse | null>(null);

  // Filter & Search states
  const [searchTerm, setSearchTerm] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<"all" | "detected" | "not_detected">("all");
  const [collapsedGroups, setCollapsedGroups] = useState<Record<string, boolean>>({});

  const toggleGroup = (groupName: string) => {
    setCollapsedGroups((prev) => ({
      ...prev,
      [groupName]: !prev[groupName],
    }));
  };

  const handleRunAnalysis = async () => {
    if (!selectedDocId) {
      setError("Please select a document from the list to analyze.");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const resp = await analyzeContract(selectedDocId, {
        confidence_threshold: confidenceThreshold,
      });
      setAnalysis(resp);
    } catch (err: any) {
      setError(err.message || "Failed to analyze contract clauses.");
      setAnalysis(null);
    } finally {
      setLoading(false);
    }
  };

  const handleJumpToClause = (clause: ClauseSpan) => {
    if (!clause.page_number) return;

    const citation: Citation = {
      citation_id: `cuad_${clause.category.toLowerCase().replace(/[^a-z0-9]+/g, "_")}`,
      doc_id: clause.doc_id,
      filename: clause.filename,
      page_number: clause.page_number,
      chunk_id: "",
      start_char: clause.start_char ?? 0,
      end_char: clause.end_char ?? (clause.extracted_text?.length ?? 0),
      supporting_excerpt: clause.extracted_text ?? "",
      boundary_type: clause.boundary_type ?? "physical",
      is_approximate: clause.is_approximate,
      relevance_score: Math.min(1.0, clause.confidence_score / 6.0),
    };

    if (onSelectCitation) {
      onSelectCitation(citation);
    } else if (onSelectDocumentPage) {
      onSelectDocumentPage(clause.doc_id, clause.page_number);
    }
  };

  const resultsMap: Record<string, ClauseSpan> = {};
  if (analysis) {
    for (const r of analysis.results) {
      resultsMap[r.category] = r;
    }
  }

  return (
    <div className="space-y-6">
      {/* Header & Academic Disclaimer Card */}
      <div className="bg-gradient-to-r from-zinc-900/90 via-slate-900/80 to-zinc-900/90 border border-zinc-800 rounded-3xl p-6 md:p-8 backdrop-blur-md shadow-2xl space-y-5">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
          <div className="flex items-start gap-4">
            <div className="p-3.5 rounded-2xl bg-gradient-to-tr from-amber-500/20 to-indigo-500/20 border border-amber-500/30 text-amber-400">
              <Scale className="w-8 h-8" />
            </div>
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-xl font-bold text-white tracking-tight">
                  Experimental Contract Intelligence
                </h2>
                <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-300 border border-amber-500/30">
                  CUAD Baseline Heuristic (41 Categories)
                </span>
                <span className="px-2.5 py-0.5 rounded-full text-[10px] font-mono bg-zinc-800 text-zinc-400 border border-zinc-700">
                  Academic NLP Demo
                </span>
              </div>
              <p className="text-xs sm:text-sm text-zinc-400 mt-1 max-w-2xl leading-relaxed">
                Evaluates legal contracts against the 41 CUAD (Contract Understanding Atticus Dataset) categories using an isolated lexical trigger extractor. Requires explicit contract selection.
              </p>
            </div>
          </div>

          {/* Quick Config / Threshold */}
          <div className="flex items-center gap-4 bg-zinc-950/60 p-3 rounded-2xl border border-zinc-800">
            <div className="text-xs">
              <span className="text-zinc-400 block">Trigger Threshold:</span>
              <span className="font-mono font-bold text-amber-400">{confidenceThreshold.toFixed(1)}</span>
            </div>
            <input
              type="range"
              min="1.0"
              max="5.0"
              step="0.5"
              value={confidenceThreshold}
              onChange={(e) => setConfidenceThreshold(parseFloat(e.target.value))}
              className="accent-amber-500 cursor-pointer w-24"
              title="Higher values enforce stricter phrase/keyword trigger overlap"
            />
          </div>
        </div>

        {/* Mandatory Academic & Legal Disclaimer */}
        <div className="p-4 rounded-2xl bg-amber-500/10 border border-amber-500/30 flex items-start gap-3 text-amber-300/90 text-xs leading-relaxed">
          <ShieldAlert className="w-5 h-5 flex-shrink-0 text-amber-400 mt-0.5" />
          <div className="space-y-1">
            <p className="font-semibold text-amber-200">
              Academic Demonstration Only — Strictly Not Legal Advice
            </p>
            <p className="text-zinc-400">
              This module operates on a reproducible heuristic trigger baseline (CUAD baseline). It does not provide legal advice, attorney review, or verified absence. A status of &quot;Not detected&quot; indicates the heuristic pattern was not identified above the trigger threshold; it does <strong className="text-zinc-300">not</strong> prove that the clause is absent from the document.
            </p>
          </div>
        </div>

        {/* Document Selection and Action Bar */}
        <div className="pt-2 border-t border-zinc-800 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3 flex-1 max-w-md">
            <label htmlFor="contract-doc-select" className="text-xs font-semibold text-zinc-300 whitespace-nowrap">
              Target Contract:
            </label>
            <select
              id="contract-doc-select"
              value={selectedDocId}
              onChange={(e) => setSelectedDocId(e.target.value)}
              className="w-full px-3 py-2 bg-zinc-950 border border-zinc-700 rounded-xl text-xs text-zinc-200 focus:outline-none focus:border-amber-500"
            >
              {indexedDocs.length === 0 ? (
                <option value="">No indexed documents found (upload first)</option>
              ) : (
                indexedDocs.map((doc) => (
                  <option key={doc.doc_id} value={doc.doc_id}>
                    {doc.filename} ({doc.total_pages}p • {doc.total_chunks} passages)
                  </option>
                ))
              )}
            </select>
          </div>

          <button
            type="button"
            id="run-contract-analysis-btn"
            onClick={handleRunAnalysis}
            disabled={loading || !selectedDocId || indexedDocs.length === 0}
            className="px-5 py-2.5 bg-gradient-to-r from-amber-500 via-amber-600 to-indigo-600 hover:from-amber-600 hover:to-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed text-white text-xs font-bold rounded-xl shadow-lg shadow-amber-500/20 transition-all flex items-center justify-center gap-2 cursor-pointer"
          >
            {loading ? (
              <>
                <svg className="animate-spin w-4 h-4 text-white" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                <span>Extracting 41 CUAD Clauses...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4 text-amber-200" />
                <span>Analyze Contract Clauses</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Error Alert */}
      {error && (
        <div className="p-4 bg-rose-500/10 border border-rose-500/30 rounded-2xl flex items-start gap-3 text-rose-300 text-sm">
          <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
          <div>
            <p className="font-semibold">Analysis Failed</p>
            <p className="text-xs text-rose-400 mt-0.5">{error}</p>
          </div>
        </div>
      )}

      {/* Analysis Results Display */}
      {analysis && (
        <div className="space-y-6" id="contract-analysis-results">
          {/* Summary Metric Cards */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="p-4 bg-zinc-900/80 border border-zinc-800 rounded-2xl">
              <span className="text-[11px] text-zinc-400 block font-medium">Document Scanned</span>
              <span className="text-sm font-bold text-white truncate block mt-1" title={analysis.filename}>
                {analysis.filename}
              </span>
              <span className="text-[10px] text-zinc-500 font-mono mt-0.5 block">
                {analysis.total_pages} page(s) • {analysis.total_chunks_scanned} chunks
              </span>
            </div>

            <div className="p-4 bg-zinc-900/80 border border-zinc-800 rounded-2xl">
              <span className="text-[11px] text-zinc-400 block font-medium">Clauses Detected</span>
              <span className="text-xl font-extrabold text-emerald-400 mt-1 block font-mono">
                {analysis.clauses_detected_count}
              </span>
              <span className="text-[10px] text-zinc-500 font-mono mt-0.5 block">
                of {analysis.categories_analyzed} CUAD categories
              </span>
            </div>

            <div className="p-4 bg-zinc-900/80 border border-zinc-800 rounded-2xl">
              <span className="text-[11px] text-zinc-400 block font-medium">No Heuristic Detection</span>
              <span className="text-xl font-extrabold text-amber-400/90 mt-1 block font-mono">
                {analysis.clauses_not_detected_count}
              </span>
              <span className="text-[10px] text-amber-500/80 block mt-0.5">
                Absence not guaranteed
              </span>
            </div>

            <div className="p-4 bg-zinc-900/80 border border-zinc-800 rounded-2xl">
              <span className="text-[11px] text-zinc-400 block font-medium">Extraction Latency</span>
              <span className="text-xl font-extrabold text-indigo-400 mt-1 block font-mono">
                {analysis.latency_ms.toFixed(1)} ms
              </span>
              <span className="text-[10px] text-zinc-500 block mt-0.5">
                Local CPU heuristic
              </span>
            </div>
          </div>

          {/* Filter and Category Search Toolbar */}
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 bg-zinc-900/60 p-3 rounded-2xl border border-zinc-800">
            <div className="relative flex-1 max-w-sm">
              <Search className="w-3.5 h-3.5 text-zinc-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Filter categories (e.g. 'liability', 'termination')..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-8 pr-3 py-1.5 bg-zinc-950 border border-zinc-800 rounded-xl text-xs text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-amber-500"
              />
            </div>

            <div className="flex items-center gap-1.5">
              <Filter className="w-3.5 h-3.5 text-zinc-400 mr-1" />
              {(["all", "detected", "not_detected"] as const).map((filterOpt) => (
                <button
                  key={filterOpt}
                  onClick={() => setStatusFilter(filterOpt)}
                  className={`px-2.5 py-1 text-xs font-semibold rounded-lg transition-colors cursor-pointer ${
                    statusFilter === filterOpt
                      ? "bg-amber-500/20 text-amber-300 border border-amber-500/40"
                      : "text-zinc-400 hover:text-white bg-zinc-800/60 hover:bg-zinc-800 border border-zinc-700/40"
                  }`}
                >
                  {filterOpt === "all"
                    ? `All (${analysis.categories_analyzed})`
                    : filterOpt === "detected"
                    ? `Detected (${analysis.clauses_detected_count})`
                    : `Not Detected (${analysis.clauses_not_detected_count})`}
                </button>
              ))}
            </div>
          </div>

          {/* Grouped Category Results */}
          <div className="space-y-4">
            {Object.entries(CATEGORY_GROUPS).map(([groupTitle, groupCategories]) => {
              // Filter categories by search term and status
              const matchingCategories = groupCategories.filter((cat) => {
                const clause = resultsMap[cat];
                if (!clause) return false;

                if (searchTerm.trim() && !cat.toLowerCase().includes(searchTerm.toLowerCase())) {
                  return false;
                }

                if (statusFilter === "detected" && !clause.detected) return false;
                if (statusFilter === "not_detected" && clause.detected) return false;

                return true;
              });

              if (matchingCategories.length === 0) return null;

              const isCollapsed = collapsedGroups[groupTitle] || false;
              const detectedInGroup = matchingCategories.filter((c) => resultsMap[c]?.detected).length;

              return (
                <div
                  key={groupTitle}
                  className="bg-zinc-900/80 border border-zinc-800/80 rounded-2xl overflow-hidden shadow-lg"
                >
                  {/* Group Header Accordion Bar */}
                  <button
                    type="button"
                    onClick={() => toggleGroup(groupTitle)}
                    className="w-full px-5 py-3.5 bg-zinc-950/60 hover:bg-zinc-950/90 flex items-center justify-between border-b border-zinc-800/60 transition-colors text-left cursor-pointer"
                  >
                    <div className="flex items-center gap-2.5">
                      {isCollapsed ? (
                        <ChevronRight className="w-4 h-4 text-zinc-400" />
                      ) : (
                        <ChevronDown className="w-4 h-4 text-amber-400" />
                      )}
                      <span className="text-xs sm:text-sm font-bold text-zinc-200">
                        {groupTitle}
                      </span>
                    </div>

                    <div className="flex items-center gap-2">
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-mono font-semibold ${
                        detectedInGroup > 0
                          ? "bg-emerald-500/10 text-emerald-300 border border-emerald-500/30"
                          : "bg-zinc-800 text-zinc-400 border border-zinc-700"
                      }`}>
                        {detectedInGroup} of {matchingCategories.length} detected
                      </span>
                    </div>
                  </button>

                  {/* Group Content */}
                  {!isCollapsed && (
                    <div className="p-4 space-y-3">
                      {matchingCategories.map((cat) => {
                        const clause = resultsMap[cat];
                        if (!clause) return null;

                        return (
                          <div
                            key={cat}
                            className={`p-4 rounded-xl border transition-all ${
                              clause.detected
                                ? "bg-zinc-950/80 border-emerald-500/30 hover:border-emerald-500/50"
                                : "bg-zinc-950/40 border-zinc-800/60 text-zinc-400"
                            }`}
                          >
                            <div className="flex flex-wrap items-center justify-between gap-3 mb-2">
                              <div className="flex flex-wrap items-center gap-2">
                                <span className={`w-2 h-2 rounded-full ${clause.detected ? "bg-emerald-400" : "bg-zinc-600"}`} />
                                <h4 className="text-xs sm:text-sm font-bold text-zinc-100">
                                  {clause.category}
                                </h4>

                                {clause.detected ? (
                                  <>
                                    <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/10 text-emerald-300 border border-emerald-500/30">
                                      Candidate Detected
                                    </span>
                                    <span className="text-[10px] font-mono text-amber-300 px-2 py-0.5 bg-amber-500/10 rounded border border-amber-500/30">
                                      Trigger Score: {clause.confidence_score.toFixed(1)}
                                    </span>
                                    {clause.page_number && (
                                      <span className="text-[10px] font-mono text-indigo-300 px-2 py-0.5 bg-indigo-500/10 rounded border border-indigo-500/30">
                                        Page {clause.page_number} (Chars {clause.start_char}–{clause.end_char})
                                      </span>
                                    )}
                                  </>
                                ) : (
                                  <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-zinc-800/80 text-zinc-400 border border-zinc-700/60">
                                    Not Detected by Heuristic
                                  </span>
                                )}
                              </div>

                              {/* Action: Jump to Document Page if detected */}
                              {clause.detected && clause.page_number && (
                                <button
                                  type="button"
                                  onClick={() => handleJumpToClause(clause)}
                                  className="px-3 py-1.5 text-xs font-semibold text-white bg-gradient-to-r from-amber-500 to-indigo-600 hover:from-amber-600 hover:to-indigo-700 rounded-lg shadow transition-all flex items-center gap-1.5 cursor-pointer"
                                >
                                  <span>View in Reader (Page {clause.page_number})</span>
                                  <ArrowRight className="w-3.5 h-3.5" />
                                </button>
                              )}
                            </div>

                            {/* Extracted Clause Text or Safe Non-Detection Notice */}
                            {clause.detected && clause.extracted_text ? (
                              <div className="mt-2.5 p-3.5 bg-zinc-900/90 border border-zinc-800 rounded-lg font-mono text-xs text-zinc-200 leading-relaxed whitespace-pre-wrap select-text">
                                &ldquo;{clause.extracted_text}&rdquo;
                              </div>
                            ) : (
                              <p className="text-[11px] text-zinc-500 italic mt-1">
                                {clause.explanation}
                              </p>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Initial Prompt State */}
      {!analysis && !loading && (
        <div className="text-center py-12 bg-zinc-900/30 border border-zinc-800/50 rounded-2xl p-6">
          <div className="w-12 h-12 rounded-2xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center mx-auto text-amber-400 mb-3">
            <Scale className="w-6 h-6" />
          </div>
          <h4 className="text-sm font-semibold text-zinc-200">
            Legal Contract Intelligence Ready
          </h4>
          <p className="text-xs text-zinc-400 mt-1 max-w-md mx-auto">
            Select an uploaded document above and click &quot;Analyze Contract Clauses&quot;. The CUAD trigger baseline will evaluate the 41 standard legal clause categories with exact character offsets and verifiable page references.
          </p>
        </div>
      )}
    </div>
  );
};
