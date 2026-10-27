"use client";

import React, { useState } from "react";
import { DocumentExtractionResponse } from "@/lib/api";
import {
  FileText,
  Layers,
  Calendar,
  User,
  Copy,
  Check,
  Download,
  ChevronLeft,
  ChevronRight,
  Search,
  Code2,
  BookOpen,
  Trash2,
  FileCheck2,
} from "lucide-react";

interface DocumentViewerProps {
  document: DocumentExtractionResponse;
  onClear: () => void;
}

export const DocumentViewer: React.FC<DocumentViewerProps> = ({
  document,
  onClear,
}) => {
  const [currentPageIndex, setCurrentPageIndex] = useState(0);
  const [activeTab, setActiveTab] = useState<"pages" | "full" | "json">("pages");
  const [copied, setCopied] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  const totalPages = document.extracted_pages.length;
  const currentPage = document.extracted_pages[currentPageIndex] || {
    page_number: 1,
    text: "",
    char_count: 0,
    word_count: 0,
  };

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownloadJson = () => {
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(document, null, 2));
    const downloadAnchor = window.document.createElement("a");
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", `${document.filename}.extraction.json`);
    window.document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  const fullText = document.extracted_pages
    .map((p) => `--- PAGE ${p.page_number} ---\n\n${p.text}`)
    .join("\n\n");

  const highlightMatches = (text: string, query: string) => {
    if (!query.trim()) return text;
    const parts = text.split(new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "gi"));
    return parts.map((part, i) =>
      part.toLowerCase() === query.toLowerCase() ? (
        <mark key={i} className="bg-amber-400 text-slate-900 px-0.5 rounded font-semibold">
          {part}
        </mark>
      ) : (
        part
      )
    );
  };

  return (
    <div className="w-full space-y-6">
      {/* Document Overview Header Card */}
      <div className="rounded-3xl bg-slate-900/70 border border-slate-800 p-6 md:p-8 backdrop-blur-md shadow-2xl">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
          <div className="flex items-start gap-4">
            <div className="p-3.5 rounded-2xl bg-gradient-to-tr from-cyan-600/30 to-blue-600/30 border border-cyan-500/30 text-cyan-400">
              <FileCheck2 className="w-8 h-8" />
            </div>
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-xl font-bold text-white tracking-tight">
                  {document.filename}
                </h2>
                <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-cyan-950 border border-cyan-800 text-cyan-400">
                  {document.file_type}
                </span>
                <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-800 border border-slate-700 text-slate-300">
                  {document.file_size_formatted}
                </span>
              </div>

              {/* Metadata Badges */}
              <div className="flex flex-wrap items-center gap-4 mt-3 text-xs text-slate-400">
                <span className="flex items-center gap-1.5">
                  <Layers className="w-3.5 h-3.5 text-indigo-400" />
                  <strong className="text-slate-200">{document.total_pages}</strong> page{document.total_pages > 1 ? "s" : ""}
                </span>
                <span className="flex items-center gap-1.5">
                  <FileText className="w-3.5 h-3.5 text-emerald-400" />
                  <strong className="text-slate-200">{document.total_words.toLocaleString()}</strong> words
                </span>
                <span className="flex items-center gap-1.5">
                  <Calendar className="w-3.5 h-3.5 text-blue-400" />
                  {document.metadata.processed_at ? new Date(document.metadata.processed_at).toLocaleTimeString() : "Just now"}
                </span>
                {document.metadata.author && (
                  <span className="flex items-center gap-1.5">
                    <User className="w-3.5 h-3.5 text-purple-400" />
                    Author: {document.metadata.author}
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Action Toolbar */}
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={() => handleCopy(activeTab === "pages" ? currentPage.text : fullText)}
              className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-slate-800/80 hover:bg-slate-700 border border-slate-700 text-xs font-medium text-slate-200 transition-all cursor-pointer"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
              <span>{copied ? "Copied!" : "Copy Text"}</span>
            </button>

            <button
              onClick={handleDownloadJson}
              className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-slate-800/80 hover:bg-slate-700 border border-slate-700 text-xs font-medium text-slate-200 transition-all cursor-pointer"
            >
              <Download className="w-3.5 h-3.5 text-cyan-400" />
              <span>Download JSON</span>
            </button>

            <button
              onClick={onClear}
              className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-rose-950/40 hover:bg-rose-950/80 border border-rose-800/60 text-xs font-medium text-rose-300 transition-all cursor-pointer"
            >
              <Trash2 className="w-3.5 h-3.5" />
              <span>Reset</span>
            </button>
          </div>
        </div>

        {/* View Switcher Tabs */}
        <div className="flex border-b border-slate-800 mt-6 pt-2 gap-4">
          <button
            onClick={() => setActiveTab("pages")}
            className={`pb-3 text-xs font-semibold flex items-center gap-1.5 transition-colors border-b-2 cursor-pointer ${
              activeTab === "pages"
                ? "border-cyan-400 text-cyan-300"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <BookOpen className="w-4 h-4" />
            Page-by-Page Reader ({totalPages})
          </button>
          <button
            onClick={() => setActiveTab("full")}
            className={`pb-3 text-xs font-semibold flex items-center gap-1.5 transition-colors border-b-2 cursor-pointer ${
              activeTab === "full"
                ? "border-cyan-400 text-cyan-300"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <FileText className="w-4 h-4" />
            Full Document Stream
          </button>
          <button
            onClick={() => setActiveTab("json")}
            className={`pb-3 text-xs font-semibold flex items-center gap-1.5 transition-colors border-b-2 cursor-pointer ${
              activeTab === "json"
                ? "border-cyan-400 text-cyan-300"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <Code2 className="w-4 h-4" />
            Structured JSON
          </button>
        </div>
      </div>

      {/* Main Content Area */}
      {activeTab === "pages" && (
        <div className="rounded-3xl bg-slate-900/60 border border-slate-800 p-6 md:p-8 backdrop-blur-md shadow-xl">
          {/* Page Controls Bar */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-slate-800">
            {/* Pagination Navigator */}
            <div className="flex items-center gap-2">
              <button
                onClick={() => setCurrentPageIndex((prev) => Math.max(0, prev - 1))}
                disabled={currentPageIndex === 0}
                className="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed border border-slate-700 text-slate-200 transition-colors cursor-pointer"
                title="Previous Page"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>

              <div className="flex items-center gap-1 text-xs font-medium text-slate-300 px-3 py-1.5 rounded-xl bg-slate-800/80 border border-slate-700">
                <span>Page</span>
                <span className="font-bold text-cyan-300">{currentPage.page_number}</span>
                <span>of</span>
                <span className="font-bold text-white">{totalPages}</span>
              </div>

              <button
                onClick={() => setCurrentPageIndex((prev) => Math.min(totalPages - 1, prev + 1))}
                disabled={currentPageIndex === totalPages - 1}
                className="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed border border-slate-700 text-slate-200 transition-colors cursor-pointer"
                title="Next Page"
              >
                <ChevronRight className="w-4 h-4" />
              </button>

              <div className="hidden md:flex items-center gap-1.5 ml-3 text-xs text-slate-400">
                <span>{currentPage.word_count.toLocaleString()} words</span>
                <span>•</span>
                <span>{currentPage.char_count.toLocaleString()} chars</span>
              </div>
            </div>

            {/* Quick Page Jump Pills */}
            <div className="flex items-center gap-1 overflow-x-auto max-w-xs sm:max-w-md py-1">
              {document.extracted_pages.map((p, idx) => (
                <button
                  key={idx}
                  onClick={() => setCurrentPageIndex(idx)}
                  className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-all cursor-pointer ${
                    currentPageIndex === idx
                      ? "bg-cyan-500 text-slate-950 font-bold shadow-md shadow-cyan-500/20"
                      : "bg-slate-800/60 hover:bg-slate-800 text-slate-400 hover:text-white"
                  }`}
                >
                  {p.page_number}
                </button>
              ))}
            </div>

            {/* In-page search */}
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Search page..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-8 pr-3 py-1.5 rounded-xl bg-slate-800/70 border border-slate-700 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500 transition-colors w-full sm:w-44"
              />
            </div>
          </div>

          {/* Page Text Viewer */}
          <div className="mt-6">
            <div className="p-6 rounded-2xl bg-slate-950/80 border border-slate-800/80 font-mono text-xs sm:text-sm text-slate-300 leading-relaxed whitespace-pre-wrap selection:bg-cyan-500/30 max-h-[600px] overflow-y-auto">
              {currentPage.text ? (
                highlightMatches(currentPage.text, searchQuery)
              ) : (
                <div className="text-center py-12 text-slate-500 font-sans">
                  <p className="text-sm font-semibold">Blank Page / No Text Detected</p>
                  <p className="text-xs mt-1">This page might contain images or vector diagrams without embedded text.</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Full Document Stream */}
      {activeTab === "full" && (
        <div className="rounded-3xl bg-slate-900/60 border border-slate-800 p-6 md:p-8 backdrop-blur-md shadow-xl">
          <div className="flex items-center justify-between pb-4 border-b border-slate-800">
            <h3 className="text-sm font-semibold text-white">Continuous Document Stream</h3>
            <span className="text-xs text-slate-400">{totalPages} Preserved Pages</span>
          </div>
          <div className="mt-4 p-6 rounded-2xl bg-slate-950/80 border border-slate-800/80 font-mono text-xs sm:text-sm text-slate-300 leading-relaxed whitespace-pre-wrap max-h-[650px] overflow-y-auto">
            {fullText}
          </div>
        </div>
      )}

      {/* Raw JSON tab */}
      {activeTab === "json" && (
        <div className="rounded-3xl bg-slate-900/60 border border-slate-800 p-6 md:p-8 backdrop-blur-md shadow-xl">
          <div className="flex items-center justify-between pb-4 border-b border-slate-800">
            <h3 className="text-sm font-semibold text-white">FastAPI Extraction Response Payload</h3>
            <span className="text-xs text-cyan-400 font-mono">application/json</span>
          </div>
          <div className="mt-4 p-6 rounded-2xl bg-slate-950/80 border border-slate-800/80 font-mono text-xs text-cyan-300/90 leading-relaxed max-h-[650px] overflow-y-auto">
            <pre>{JSON.stringify(document, null, 2)}</pre>
          </div>
        </div>
      )}
    </div>
  );
};
