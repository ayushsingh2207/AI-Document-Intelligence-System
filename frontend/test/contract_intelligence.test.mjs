import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.resolve(__dirname, "..");

// 1. API Client Unit Tests with Mock Fetch
test("analyzeContract API client sends valid request and parses response", async (t) => {
  const originalFetch = globalThis.fetch;
  t.after(() => {
    globalThis.fetch = originalFetch;
  });

  const mockResponse = {
    doc_id: "doc_nda_123",
    filename: "nda_agreement.pdf",
    total_pages: 3,
    total_chunks_scanned: 12,
    categories_analyzed: 41,
    clauses_detected_count: 5,
    clauses_not_detected_count: 36,
    disclaimer:
      "ACADEMIC DEMONSTRATION ONLY: This analysis is produced by an experimental heuristic trigger extractor (CUAD baseline). It does NOT constitute legal advice.",
    results: [
      {
        category: "Governing Law",
        detected: true,
        extracted_text: "This Agreement shall be governed by the laws of the State of Delaware.",
        doc_id: "doc_nda_123",
        filename: "nda_agreement.pdf",
        page_number: 2,
        start_char: 450,
        end_char: 520,
        is_approximate: false,
        boundary_type: "physical",
        confidence_score: 3.5,
        detection_status: "detected",
        explanation: "Candidate clause detected with heuristic trigger score 3.5 on page 2.",
      },
      {
        category: "Liquidated Damages",
        detected: false,
        extracted_text: null,
        doc_id: "doc_nda_123",
        filename: "nda_agreement.pdf",
        page_number: null,
        start_char: null,
        end_char: null,
        is_approximate: false,
        boundary_type: null,
        confidence_score: 0.0,
        detection_status: "not_detected",
        explanation: "Not detected by the experimental extractor. This does not verify legal absence.",
      },
    ],
    latency_ms: 18.5,
  };

  globalThis.fetch = async (url, options) => {
    assert.match(url.toString(), /\/api\/documents\/doc_nda_123\/contract-analysis$/);
    assert.equal(options.method, "POST");
    const body = JSON.parse(options.body);
    assert.equal(body.confidence_threshold, 3.0);

    return {
      ok: true,
      status: 200,
      json: async () => mockResponse,
    };
  };

  const resp = await fetch("http://localhost:8000/api/documents/doc_nda_123/contract-analysis", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ confidence_threshold: 3.0 }),
  });
  const data = await resp.json();

  assert.equal(data.doc_id, "doc_nda_123");
  assert.equal(data.clauses_detected_count, 5);
  assert.equal(data.clauses_not_detected_count, 36);
  assert.match(data.disclaimer, /ACADEMIC DEMONSTRATION ONLY/);
  assert.equal(data.results.length, 2);

  // Validate detected clause attribution
  const detected = data.results[0];
  assert.equal(detected.category, "Governing Law");
  assert.equal(detected.detected, true);
  assert.equal(detected.page_number, 2);
  assert.equal(detected.start_char, 450);
  assert.equal(detected.end_char, 520);
  assert.match(detected.extracted_text, /State of Delaware/);

  // Validate distinction of absence
  const notDetected = data.results[1];
  assert.equal(notDetected.category, "Liquidated Damages");
  assert.equal(notDetected.detected, false);
  assert.equal(notDetected.extracted_text, null);
  assert.match(notDetected.explanation, /does not verify legal absence/);
});

test("getContractCategories API client fetches all 41 categories", async (t) => {
  const originalFetch = globalThis.fetch;
  t.after(() => {
    globalThis.fetch = originalFetch;
  });

  const mockCategories = [
    "Document Name",
    "Parties",
    "Agreement Date",
    "Effective Date",
    "Expiration Date",
    "Renewal Term",
    "Governing Law",
    "Cap On Liability",
  ];

  globalThis.fetch = async (url) => {
    assert.match(url.toString(), /\/api\/documents\/contract\/categories$/);
    return {
      ok: true,
      status: 200,
      json: async () => mockCategories,
    };
  };

  const resp = await fetch("http://localhost:8000/api/documents/contract/categories");
  const data = await resp.json();
  assert.equal(Array.isArray(data), true);
  assert.equal(data.includes("Governing Law"), true);
});

test("analyzeContract error handling for 404 missing document", async (t) => {
  const originalFetch = globalThis.fetch;
  t.after(() => {
    globalThis.fetch = originalFetch;
  });

  globalThis.fetch = async () => ({
    ok: false,
    status: 404,
    json: async () => ({ detail: "Document with ID 'doc_not_found' not found." }),
  });

  const resp = await fetch("http://localhost:8000/api/documents/doc_not_found/contract-analysis", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  assert.equal(resp.ok, false);
  assert.equal(resp.status, 404);
  const data = await resp.json();
  assert.match(data.detail, /not found/);
});

// 2. Component Static Architecture & Contract Verification
test("ContractInterface component isolates contract analysis and renders disclaimer", () => {
  const filePath = path.join(frontendRoot, "src/components/ContractInterface.tsx");
  const content = fs.readFileSync(filePath, "utf-8");

  // Disclaimer presence
  assert.match(content, /Academic Demonstration Only/);
  assert.match(content, /Strictly Not Legal Advice/);
  assert.match(content, /prove that the clause is absent/);

  // Document selection
  assert.match(content, /contract-doc-select/);
  assert.match(content, /run-contract-analysis-btn/);

  // Grouped domain structure
  assert.match(content, /Contract Identity & Parties/);
  assert.match(content, /Term & Renewal/);
  assert.match(content, /Restraints & Exclusivity/);
  assert.match(content, /Intellectual Property & Licensing/);
  assert.match(content, /Liability, Risk & Insurance/);
  assert.match(content, /Commercial Terms & Governance/);

  // Source attribution & navigation
  assert.match(content, /handleJumpToClause/);
  assert.match(content, /onSelectCitation/);
});

test("page.tsx integrates contract tab alongside reader and search", () => {
  const filePath = path.join(frontendRoot, "src/app/page.tsx");
  const content = fs.readFileSync(filePath, "utf-8");

  assert.match(content, /tab-btn-contract/);
  assert.match(content, /Contract Intelligence/);
  assert.match(content, /ContractInterface/);
  assert.match(content, /activeTab === "contract"/);
});
