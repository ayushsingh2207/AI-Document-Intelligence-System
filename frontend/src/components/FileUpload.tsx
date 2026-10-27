"use client";

import React, { useState, useRef } from "react";
import { UploadCloud, FileType, CheckCircle2, AlertTriangle, Sparkles, Loader2 } from "lucide-react";
import { uploadDocument, DocumentExtractionResponse } from "@/lib/api";

interface FileUploadProps {
  onUploadSuccess: (data: DocumentExtractionResponse) => void;
  maxSizeMb: number;
}

export const FileUpload: React.FC<FileUploadProps> = ({
  onUploadSuccess,
  maxSizeMb,
}) => {
  const [isDragging, setIsDragging] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [uploadedFileName, setUploadedFileName] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const maxSizeBytes = maxSizeMb * 1024 * 1024;

  const validateAndProcessFile = async (file: File) => {
    setErrorMessage(null);

    // 1. Check extension
    const nameLower = file.name.toLowerCase();
    const isSupported =
      nameLower.endsWith(".pdf") ||
      nameLower.endsWith(".docx") ||
      nameLower.endsWith(".txt");

    if (!isSupported) {
      setErrorMessage(
        `Unsupported file type. AI Document Intelligence only accepts .PDF, .DOCX, and .TXT documents.`
      );
      return;
    }

    // 2. Check size
    if (file.size === 0) {
      setErrorMessage("The selected file is empty (0 bytes). Please upload a valid document.");
      return;
    }

    if (file.size > maxSizeBytes) {
      setErrorMessage(
        `File is too large (${(file.size / (1024 * 1024)).toFixed(1)} MB). The maximum allowed upload size is ${maxSizeMb} MB.`
      );
      return;
    }

    // 3. Upload to backend
    setIsLoading(true);
    setUploadedFileName(file.name);
    try {
      const response = await uploadDocument(file);
      onUploadSuccess(response);
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to upload and process the document.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const files = e.dataTransfer.files;
    if (files && files.length > 0) {
      validateAndProcessFile(files[0]);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      validateAndProcessFile(files[0]);
    }
    // reset input so same file can be re-selected if desired
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  // Demo file helpers to quickly test without looking for local files
  const handleLoadDemo = (type: "single" | "multi") => {
    let content = "";
    let filename = "";

    if (type === "single") {
      filename = "quarterly_executive_summary.txt";
      content = `AI DOCUMENT INTELLIGENCE SYSTEM - EXECUTIVE BRIEFING
Document ID: DOC-2026-X1
Status: Approved for Phase 1 Deployment
Classification: Internal NLP Pipeline

1. EXECUTIVE SUMMARY
This document outlines the core architecture of the Phase 1 Ingestion and Text Extraction Engine. The objective is to establish an ultra-reliable, zero-cost processing pipeline that validates incoming document binaries (PDF, DOCX, TXT) using deep magic-byte inspection while accurately preserving page-level demarcations.

2. PIPELINE SPECIFICATIONS
- Validation Layer: Performs MIME-type verification, null-byte checks, and ZIP-integrity validation for OpenXML containers.
- Extraction Layer: Employs pure-Python extraction libraries (pypdf, python-docx, standard UTF-8 stream decoders) without reliance on external or paid cloud APIs.
- Security Policies: Enforces path-traversal sanitization and strict chunked file-size caps (15MB).

3. PHASE 1 MILESTONES
- Zero paid API dependencies
- 100% deterministic test coverage
- End-to-end integration between FastAPI backend and Next.js reactive frontend.`;
    } else {
      filename = "comprehensive_ml_research_report.txt";
      content = `RESEARCH REPORT: ADVANCED DOCUMENT REPRESENTATION
Section: Natural Language Processing
Date: October 2026

Page 1 Overview:
Document intelligence represents a confluence of computational linguistics, structural parsing, and semantic extraction. Traditional optical character recognition (OCR) systems frequently lose layout hierarchy, paragraph structures, and physical page demarcations. In our system, Phase 1 prioritizes preserving native document structures before any vectorization or embeddings are calculated in Phase 2.
\x0c
Page 2: Extraction Methodologies and Benchmark Metrics
In evaluating PDF text streams versus rendered raster images, text stream extraction yields zero tokenization noise for digital-first documents.

Benchmark Metrics:
- Ingestion Latency: < 25ms per page
- Word Count Accuracy: 99.8% across non-scanned legal and scientific corpora
- Form Feed Delimited Chunks: Preserves native 1-indexed pagination.
\x0c
Page 3: Security & Deployment Architecture
The pipeline operates strictly in memory without persistent file retention on disk, complying with data privacy mandates. The microservice is hosted on containerized Python runtimes with CORS policy lockdown.`;
    }

    const blob = new Blob([content], { type: "text/plain" });
    const file = new File([blob], filename, { type: "text/plain" });
    validateAndProcessFile(file);
  };

  return (
    <div className="w-full">
      {/* Upload Box */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => !isLoading && fileInputRef.current?.click()}
        className={`relative overflow-hidden rounded-3xl border-2 border-dashed p-8 md:p-12 text-center cursor-pointer transition-all duration-300 ${
          isDragging
            ? "border-cyan-400 bg-cyan-950/20 scale-[1.01] shadow-2xl shadow-cyan-500/10"
            : isLoading
            ? "border-slate-700 bg-slate-900/40 cursor-wait"
            : "border-slate-800 hover:border-slate-600 bg-slate-900/40 hover:bg-slate-900/60 shadow-xl"
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.docx,.txt"
          onChange={handleFileChange}
          className="hidden"
          disabled={isLoading}
        />

        <div className="flex flex-col items-center justify-center max-w-lg mx-auto">
          {/* Animated Icon Circle */}
          <div
            className={`w-16 h-16 rounded-2xl flex items-center justify-center mb-5 transition-transform duration-300 ${
              isLoading
                ? "bg-cyan-500/10 text-cyan-400"
                : isDragging
                ? "bg-cyan-500 text-white scale-110"
                : "bg-slate-800 text-slate-300 group-hover:scale-105"
            }`}
          >
            {isLoading ? (
              <Loader2 className="w-8 h-8 animate-spin text-cyan-400" />
            ) : (
              <UploadCloud className="w-8 h-8 text-cyan-400" />
            )}
          </div>

          {/* Heading & Subtitle */}
          {isLoading ? (
            <div>
              <h3 className="text-lg font-semibold text-white">
                Processing Document...
              </h3>
              <p className="text-sm text-cyan-400 mt-1 font-mono">
                {uploadedFileName}
              </p>
              <p className="text-xs text-slate-400 mt-2">
                Validating file signatures & extracting structured page contents...
              </p>
            </div>
          ) : (
            <div>
              <h3 className="text-lg font-semibold text-white">
                Drag & drop your document here, or{" "}
                <span className="text-cyan-400 hover:underline">browse</span>
              </h3>
              <p className="text-xs text-slate-400 mt-1.5">
                Maximum file size: {maxSizeMb} MB. Text & page structures are extracted securely.
              </p>

              {/* Supported Format Badges */}
              <div className="flex items-center justify-center gap-2 mt-5">
                <span className="px-2.5 py-1 rounded-lg text-xs font-medium bg-red-950/60 border border-red-800/60 text-red-300 flex items-center gap-1.5">
                  <FileType className="w-3.5 h-3.5" /> PDF
                </span>
                <span className="px-2.5 py-1 rounded-lg text-xs font-medium bg-blue-950/60 border border-blue-800/60 text-blue-300 flex items-center gap-1.5">
                  <FileType className="w-3.5 h-3.5" /> DOCX
                </span>
                <span className="px-2.5 py-1 rounded-lg text-xs font-medium bg-emerald-950/60 border border-emerald-800/60 text-emerald-300 flex items-center gap-1.5">
                  <FileType className="w-3.5 h-3.5" /> TXT
                </span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Error Alert Banner */}
      {errorMessage && (
        <div className="mt-4 p-4 rounded-2xl bg-rose-950/50 border border-rose-800/80 text-rose-200 text-sm flex items-start gap-3 animate-in fade-in duration-200">
          <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
          <div className="flex-1">
            <p className="font-semibold text-rose-300">Validation Notice</p>
            <p className="text-xs text-rose-200/90 mt-0.5">{errorMessage}</p>
          </div>
          <button
            onClick={() => setErrorMessage(null)}
            className="text-xs text-rose-400 hover:text-white px-2 py-1 rounded-lg bg-rose-900/40 hover:bg-rose-900/80 transition-colors"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Quick Demo Pre-load Bar */}
      <div className="mt-4 flex flex-wrap items-center justify-between gap-3 px-2 text-xs text-slate-400">
        <div className="flex items-center gap-2">
          <Sparkles className="w-3.5 h-3.5 text-amber-400" />
          <span>Need a sample to test?</span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={(e) => {
              e.stopPropagation();
              handleLoadDemo("single");
            }}
            disabled={isLoading}
            className="px-3 py-1.5 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-800 hover:border-slate-700 text-slate-200 transition-colors cursor-pointer disabled:opacity-50"
          >
            Load 1-Page Briefing
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation();
              handleLoadDemo("multi");
            }}
            disabled={isLoading}
            className="px-3 py-1.5 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-800 hover:border-slate-700 text-slate-200 transition-colors cursor-pointer disabled:opacity-50"
          >
            Load 3-Page Research Report
          </button>
        </div>
      </div>
    </div>
  );
};
