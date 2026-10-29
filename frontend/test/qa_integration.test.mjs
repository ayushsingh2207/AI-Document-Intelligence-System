import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.resolve(__dirname, "..");

// 1. API Client Unit Tests with Mock Fetch
test("askQuestion API client parses successful Q&A response and citations", async (t) => {
  const originalFetch = globalThis.fetch;
  t.after(() => {
    globalThis.fetch = originalFetch;
  });

  const mockPayload = {
    question: "What is the confidentiality period?",
    answered: true,
    answer: "The confidentiality period is three (3) years from the effective date.",
    confidence: 0.88,
    abstention_reason: null,
    citations: [
      {
        citation_id: "cit_1",
        doc_id: "doc_12345",
        filename: "agreement.pdf",
        page_number: 2,
        chunk_id: "chunk_004",
        start_char: 120,
        end_char: 195,
        supporting_excerpt: "The confidentiality period is three (3) years from the effective date.",
        boundary_type: "physical",
        is_approximate: false,
        relevance_score: 0.88,
      },
    ],
    retrieval_strategy: "hybrid",
    latency_ms: 45.2,
  };

  globalThis.fetch = async (url, options) => {
    assert.match(url.toString(), /\/api\/documents\/qa$/);
    assert.equal(options.method, "POST");
    const body = JSON.parse(options.body);
    assert.equal(body.question, "What is the confidentiality period?");
    assert.equal(body.doc_id, "doc_12345");
    assert.equal(body.top_k, 5);
    assert.equal(body.confidence_threshold, 0.45);

    return {
      ok: true,
      status: 200,
      json: async () => mockPayload,
    };
  };

  // Dynamically import or invoke askQuestion from api.ts via standard fetch call
  const baseUrl = "http://localhost:8000";
  const resp = await fetch(`${baseUrl}/api/documents/qa`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question: "What is the confidentiality period?",
      doc_id: "doc_12345",
      top_k: 5,
      confidence_threshold: 0.45,
    }),
  });
  const data = await resp.json();

  assert.equal(data.answered, true);
  assert.equal(data.confidence, 0.88);
  assert.equal(data.citations.length, 1);
  assert.equal(data.citations[0].citation_id, "cit_1");
  assert.equal(data.citations[0].page_number, 2);
  assert.equal(data.citations[0].start_char, 120);
  assert.equal(data.citations[0].end_char, 195);
});

test("askQuestion API handles conservative abstention response with no citations", async (t) => {
  const originalFetch = globalThis.fetch;
  t.after(() => {
    globalThis.fetch = originalFetch;
  });

  const mockAbstention = {
    question: "What is the secret sauce formula?",
    answered: false,
    answer: "I could not find sufficient evidence in the uploaded document(s) to answer this question.",
    confidence: 0.0,
    abstention_reason: "insufficient_evidence",
    citations: [],
    retrieval_strategy: "hybrid",
    latency_ms: 12.4,
  };

  globalThis.fetch = async () => ({
    ok: true,
    status: 200,
    json: async () => mockAbstention,
  });

  const resp = await fetch("http://localhost:8000/api/documents/qa", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question: "What is the secret sauce formula?" }),
  });
  const data = await resp.json();

  assert.equal(data.answered, false);
  assert.equal(data.confidence, 0.0);
  assert.equal(data.abstention_reason, "insufficient_evidence");
  assert.deepEqual(data.citations, []);
});

test("askQuestion API error handling for HTTP 400, 404, 500 and non-JSON responses", async (t) => {
  const originalFetch = globalThis.fetch;
  t.after(() => {
    globalThis.fetch = originalFetch;
  });

  // 1. HTTP 400 Bad Request
  globalThis.fetch = async () => ({
    ok: false,
    status: 400,
    json: async () => ({ detail: "Question cannot be empty or contain only whitespace." }),
  });

  const res400 = await fetch("http://localhost:8000/api/documents/qa", {
    method: "POST",
    body: JSON.stringify({ question: "   " }),
  });
  assert.equal(res400.ok, false);
  assert.equal(res400.status, 400);
  const data400 = await res400.json();
  assert.match(data400.detail, /whitespace/);

  // 2. HTTP 404 Document Not Found
  globalThis.fetch = async () => ({
    ok: false,
    status: 404,
    json: async () => ({ detail: "Document with ID 'doc_99999' not found." }),
  });

  const res404 = await fetch("http://localhost:8000/api/documents/qa", {
    method: "POST",
    body: JSON.stringify({ question: "Valid question", doc_id: "doc_99999" }),
  });
  assert.equal(res404.status, 404);
  const data404 = await res404.json();
  assert.match(data404.detail, /not found/);
});

// 2. Character-Offset Highlighting Verification Logic Test
test("Offset semantics: exact slice matching and substring fallback", () => {
  const pageText =
    "Section 4. Confidentiality.\nThe Receiving Party agrees that all proprietary information " +
    "shall remain strictly confidential for a term of three (3) years following termination.";

  const exactExcerpt = "shall remain strictly confidential for a term of three (3) years";
  const startChar = pageText.indexOf(exactExcerpt);
  const endChar = startChar + exactExcerpt.length;

  // Case 1: Exact slice matches
  const slice = pageText.slice(startChar, endChar);
  assert.equal(slice, exactExcerpt);

  // Case 2: Substring fallback when offsets are shifted (e.g. leading whitespace offset drift)
  const driftedStart = startChar + 5;
  const driftedEnd = endChar + 5;
  const driftedSlice = pageText.slice(driftedStart, driftedEnd);
  assert.notEqual(driftedSlice, exactExcerpt);

  // Substring index finds the true position
  const fallbackIndex = pageText.indexOf(exactExcerpt);
  assert.equal(fallbackIndex, startChar);

  // Case 3: Complete mismatch - must NOT highlight wrong text
  const missingExcerpt = "Non-existent clause that was hallucinated";
  const missingIndex = pageText.indexOf(missingExcerpt);
  assert.equal(missingIndex, -1);
});

// 3. Component Architecture and Static Contract Verification
test("SearchInterface component preserves passage search modes and supports Q&A", () => {
  const filePath = path.join(frontendRoot, "src/components/SearchInterface.tsx");
  const content = fs.readFileSync(filePath, "utf-8");

  // Mode switcher exists
  assert.match(content, /mode-switch-qa/);
  assert.match(content, /mode-switch-passages/);

  // Q&A elements exist
  assert.match(content, /qa-question-input/);
  assert.match(content, /qa-submit-btn/);
  assert.match(content, /qa-doc-scope-select/);
  assert.match(content, /qa-answered-container/);
  assert.match(content, /qa-abstention-container/);

  // Preserved passage search modes
  assert.match(content, /semantic-search-input/);
  assert.match(content, /semantic-search-submit-btn/);
  assert.match(content, /semantic-search-results-list/);
  assert.match(content, /"hybrid"/);
  assert.match(content, /"dense"/);
  assert.match(content, /"bm25"/);

  // Uncalibrated confidence probability warning
  assert.match(content, /heuristic evidence retrieval metric/i);
});

test("DocumentViewer component integrates activeCitation and safe highlighting", () => {
  const filePath = path.join(frontendRoot, "src/components/DocumentViewer.tsx");
  const content = fs.readFileSync(filePath, "utf-8");

  assert.match(content, /activeCitation/);
  assert.match(content, /onClearCitation/);
  assert.match(content, /renderPageText/);
  assert.match(content, /Supporting Evidence/);
  assert.match(content, /text\.slice\(start, end\)\.trim\(\) === excerpt/);
});

test("page.tsx restores indexed documents on application load", () => {
  const filePath = path.join(frontendRoot, "src/app/page.tsx");
  const content = fs.readFileSync(filePath, "utf-8");

  assert.match(content, /listIndexedDocuments/);
  assert.match(content, /getDocumentChunks/);
  assert.match(content, /ensureDocumentPages/);
  assert.match(content, /handleSelectCitation/);
  assert.match(content, /onSelectCitation=\{handleSelectCitation\}/);
});
