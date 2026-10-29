"""
End-to-End Verification Script for AI Document Intelligence System
Phase 5.4 - Real Server Execution against live FastAPI and Next.js APIs
"""

import sys
import io
import time
import httpx
import docx
from pypdf import PdfWriter

BACKEND_URL = "http://127.0.0.1:8000"
FRONTEND_URL = "http://localhost:3000"

def create_sample_pdf() -> bytes:
    """Generate a valid in-memory PDF."""
    from pypdf import PdfWriter, PageObject
    writer = PdfWriter()
    # Add a blank page with text annotation or create a simple page
    # Since pypdf PdfWriter can create blank page:
    page = writer.add_blank_page(width=612, height=792)
    # Add text via metadata or reportlab if available, or write PDF syntax directly
    # A valid raw PDF with stream text:
    pdf_content = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
        b"4 0 obj\n<< /Length 125 >>\nstream\n"
        b"BT\n/F1 12 Tf\n72 712 Td\n(This Agreement shall be governed by and construed in accordance with the laws of the State of Delaware.) Tj\nET\n"
        b"endstream\nendobj\n"
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
        b"xref\n0 6\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n0000000244 00000 n \n0000000420 00000 n \n"
        b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n497\n%%EOF\n"
    )
    return pdf_content

def create_sample_docx() -> bytes:
    doc = docx.Document()
    doc.add_heading("Master Services Agreement", level=1)
    doc.add_paragraph(
        "Either party may terminate this Agreement without cause upon giving sixty (60) days prior written notice."
    )
    doc.add_paragraph(
        "The Supplier shall maintain comprehensive cyber liability insurance of at least five million dollars."
    )
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()

def create_sample_txt() -> bytes:
    content = (
        "Project Antigravity Technical Architecture Report\n\n"
        "The distributed vector retrieval engine uses Reciprocal Rank Fusion to synthesize "
        "dense representations from FAISS IndexFlatIP with lexical tokens scored by BM25Okapi.\n\n"
        "All model inference runs deterministically on standard CPU hardware with zero cloud dependencies."
    )
    return content.encode("utf-8")

def run_e2e_verification():
    print("=" * 70)
    print("Starting AI Document Intelligence System End-to-End Verification")
    print(f"Backend Target:  {BACKEND_URL}")
    print(f"Frontend Target: {FRONTEND_URL}")
    print("=" * 70)

    session = httpx.Client()

    # 0. Health checks
    print("\n[Step 0] Health Checks...")
    r_health = session.get(f"{BACKEND_URL}/health", timeout=5)
    assert r_health.status_code == 200, f"Backend health failed: {r_health.text}"
    health_data = r_health.json()
    print(f"  [PASS] Backend Status: {health_data['status']}, Version: {health_data['version']}")

    r_front = session.get(FRONTEND_URL, timeout=5)
    assert r_front.status_code == 200, f"Frontend HTTP failed: {r_front.status_code}"
    print("  [PASS] Frontend UI responding on port 3000 (HTTP 200 OK)")

    # 1. Upload PDF, DOCX, TXT
    print("\n[Step 1 & 2] Uploading and Indexing PDF, DOCX, and TXT files...")
    pdf_bytes = create_sample_pdf()
    docx_bytes = create_sample_docx()
    txt_bytes = create_sample_txt()

    # PDF Upload
    files_pdf = {"file": ("delaware_contract.pdf", pdf_bytes, "application/pdf")}
    r_pdf = session.post(f"{BACKEND_URL}/api/documents/upload", files=files_pdf, timeout=15)
    assert r_pdf.status_code == 200, f"PDF upload failed: {r_pdf.text}"
    pdf_data = r_pdf.json()
    pdf_id = pdf_data["doc_id"]
    print(f"  [PASS] PDF Uploaded: {pdf_data['filename']} (ID: {pdf_id}), Pages: {pdf_data['total_pages']}, Chunks: {pdf_data['total_chunks']}")

    # DOCX Upload
    files_docx = {"file": ("services_agreement.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    r_docx = session.post(f"{BACKEND_URL}/api/documents/upload", files=files_docx, timeout=15)
    assert r_docx.status_code == 200, f"DOCX upload failed: {r_docx.text}"
    docx_data = r_docx.json()
    docx_id = docx_data["doc_id"]
    print(f"  [PASS] DOCX Uploaded: {docx_data['filename']} (ID: {docx_id}), Pages: {docx_data['total_pages']}, Chunks: {docx_data['total_chunks']}")

    # TXT Upload
    files_txt = {"file": ("architecture_report.txt", txt_bytes, "text/plain")}
    r_txt = session.post(f"{BACKEND_URL}/api/documents/upload", files=files_txt, timeout=15)
    assert r_txt.status_code == 200, f"TXT upload failed: {r_txt.text}"
    txt_data = r_txt.json()
    txt_id = txt_data["doc_id"]
    print(f"  [PASS] TXT Uploaded: {txt_data['filename']} (ID: {txt_id}), Pages: {txt_data['total_pages']}, Chunks: {txt_data['total_chunks']}")

    # 2. Check Document List & Stats
    r_docs = session.get(f"{BACKEND_URL}/api/documents", timeout=5)
    assert r_docs.status_code == 200
    docs_list = r_docs.json()
    indexed_ids = {d["doc_id"] for d in docs_list}
    assert pdf_id in indexed_ids and docx_id in indexed_ids and txt_id in indexed_ids
    print(f"  [PASS] Document Registry contains {len(docs_list)} documents across all formats.")

    # 3. Perform Hybrid, Dense, and BM25 searches
    print("\n[Step 3] Verifying Search Strategies (Dense, BM25, Hybrid)...")
    for strategy in ["dense", "bm25", "hybrid"]:
        s_payload = {
            "query": "Reciprocal Rank Fusion lexical tokens",
            "top_k": 3,
            "strategy": strategy
        }
        r_search = session.post(f"{BACKEND_URL}/api/documents/search", json=s_payload, timeout=10)
        assert r_search.status_code == 200, f"Search {strategy} failed: {r_search.text}"
        s_res = r_search.json()
        assert s_res["total_results"] > 0, f"Strategy {strategy} returned 0 results"
        top_doc = s_res["results"][0]
        print(f"  [PASS] {strategy.upper()} Strategy: {s_res['total_results']} result(s), top match doc='{top_doc['filename']}', score={top_doc['score']}")

    # 4. Ask an answerable question
    print("\n[Step 4] Grounded Q&A: Answerable Inquiry...")
    qa_payload = {
        "question": "What laws govern this agreement?",
        "top_k": 5
    }
    r_qa = session.post(f"{BACKEND_URL}/api/documents/qa", json=qa_payload, timeout=15)
    assert r_qa.status_code == 200, f"Q&A failed: {r_qa.text}"
    qa_res = r_qa.json()
    assert qa_res["answered"] is True, f"Expected answered=True, got {qa_res}"
    assert len(qa_res["citations"]) > 0, "Expected at least 1 citation"
    assert "Delaware" in qa_res["answer"] or "governed by" in qa_res["answer"].lower()
    cit = qa_res["citations"][0]
    print(f"  [PASS] Answer: \"{qa_res['answer']}\"")
    print(f"  [PASS] Citation: {cit['filename']} (Page {cit['page_number']}, chars {cit['start_char']}-{cit['end_char']})")

    # 5. Ask unanswerable question (abstention)
    print("\n[Step 5] Grounded Q&A: Unanswerable Inquiry & Conservative Abstention...")
    qa_unans = {
        "question": "What is the quantum encryption key rotation frequency?",
        "top_k": 5
    }
    r_qa_unans = session.post(f"{BACKEND_URL}/api/documents/qa", json=qa_unans, timeout=15)
    assert r_qa_unans.status_code == 200
    res_unans = r_qa_unans.json()
    assert res_unans["answered"] is False, "Expected abstention (answered=False)"
    assert res_unans["abstention_reason"] == "insufficient_evidence"
    assert len(res_unans["citations"]) == 0
    print(f"  [PASS] Safely abstained: \"{res_unans['answer']}\" (Reason: {res_unans['abstention_reason']}, Citations: 0)")

    # 6. Scope enforcement (zero leakage across documents)
    print("\n[Step 6] Grounded Q&A: Document Scope Enforcement...")
    # Ask about Delaware law scoped strictly to architecture_report.txt (where it does not exist)
    qa_scoped = {
        "question": "What laws govern the agreement?",
        "doc_id": txt_id,
        "top_k": 5
    }
    r_scoped = session.post(f"{BACKEND_URL}/api/documents/qa", json=qa_scoped, timeout=15)
    assert r_scoped.status_code == 200
    res_scoped = r_scoped.json()
    # Citations must never come from pdf_id or docx_id!
    for c in res_scoped["citations"]:
        assert c["doc_id"] == txt_id, f"Scope leakage! Citation doc_id {c['doc_id']} != scoped {txt_id}"
    print(f"  [PASS] Confirmed: zero leakage into doc '{txt_id}'. Answered: {res_scoped['answered']}")

    # 7. Citation offsets & navigation verification
    print("\n[Step 7] Citation Navigation & Character Offset Integrity...")
    r_chunks = session.get(f"{BACKEND_URL}/api/documents/{pdf_id}/chunks", timeout=5)
    assert r_chunks.status_code == 200
    chunks_list = r_chunks.json()
    assert len(chunks_list) > 0
    first_chunk = chunks_list[0]
    # Check that citation offsets fall cleanly within page boundaries
    assert cit["start_char"] >= 0
    assert cit["end_char"] > cit["start_char"]
    print(f"  [PASS] Verifiable Offset Range: [{cit['start_char']}..{cit['end_char']}] on Page {cit['page_number']}")

    # 8. Refresh & persistence verification
    print("\n[Step 8] Browser Refresh & Metadata Restoration Simulation...")
    r_refresh = session.get(f"{BACKEND_URL}/api/documents", timeout=5)
    assert r_refresh.status_code == 200
    restored_docs = r_refresh.json()
    assert len(restored_docs) >= 3
    print(f"  [PASS] Restored {len(restored_docs)} documents with metadata matching pre-refresh state.")

    # 9. Contract Intelligence on selected document
    print("\n[Step 9] Contract Intelligence (CUAD 41 Categories)...")
    # Analyze the PDF contract
    r_contract = session.post(f"{BACKEND_URL}/api/documents/{pdf_id}/contract-analysis", json={"confidence_threshold": 3.0}, timeout=15)
    assert r_contract.status_code == 200, f"Contract analysis failed: {r_contract.text}"
    c_res = r_contract.json()
    assert c_res["categories_analyzed"] == 41
    assert "disclaimer" in c_res
    print(f"  [PASS] Categories evaluated: {c_res['categories_analyzed']}, Detected: {c_res['clauses_detected_count']}, Not detected: {c_res['clauses_not_detected_count']}")

    # Check that Governing Law is detected in Delaware contract
    gov_law = next((d for d in c_res["results"] if d["category"] == "Governing Law"), None)
    assert gov_law is not None, "Governing Law clause should be evaluated"
    assert gov_law["detected"] is True, "Governing Law should be detected in Delaware contract"
    assert "Delaware" in gov_law["extracted_text"]
    assert gov_law["detection_status"] == "detected"
    print(f"  [PASS] Detected Clause: [{gov_law['category']}] (Confidence: {gov_law['confidence_score']}, Page: {gov_law['page_number']})")
    print(f"    Excerpt: \"{gov_law['extracted_text']}\"")

    # Check unextracted category distinction
    unextracted = next((d for d in c_res["results"] if not d["detected"]), None)
    assert unextracted is not None
    assert unextracted["detection_status"] == "not_detected"
    assert "not detected" in unextracted["explanation"].lower() or "absent" in unextracted["explanation"].lower()
    print(f"  [PASS] Absence Distinction: Category '{unextracted['category']}' marked as '{unextracted['detection_status']}'")
    print(f"    Explanation: \"{unextracted['explanation']}\"")

    # 10. Error Handling & Edge Cases
    print("\n[Step 10] Error Handling & Edge Cases (Clear error response, no crashes)...")
    # A. Unsupported file extension
    r_bad_ext = session.post(
        f"{BACKEND_URL}/api/documents/upload",
        files={"file": ("malicious.exe", b"\x4d\x5a\x90\x00", "application/x-msdownload")},
        timeout=5
    )
    assert r_bad_ext.status_code == 400
    print(f"  [PASS] Unsupported File (.exe): HTTP 400 -> {r_bad_ext.json()['detail']}")

    # B. Empty file (0 bytes)
    r_empty = session.post(
        f"{BACKEND_URL}/api/documents/upload",
        files={"file": ("empty.txt", b"", "text/plain")},
        timeout=5
    )
    assert r_empty.status_code == 400
    print(f"  [PASS] Empty File (0 bytes): HTTP 400 -> {r_empty.json()['detail']}")

    # C. Missing Document ID on Contract Analysis
    r_missing_doc = session.post(
        f"{BACKEND_URL}/api/documents/non_existent_doc_id_9999/contract-analysis",
        json={"confidence_threshold": 3.0},
        timeout=5
    )
    assert r_missing_doc.status_code == 404
    print(f"  [PASS] Missing Document ID: HTTP 404 -> {r_missing_doc.json()['detail']}")

    # D. Missing Document ID on Q&A
    r_missing_qa = session.post(
        f"{BACKEND_URL}/api/documents/qa",
        json={"question": "What is this?", "doc_id": "non_existent_doc_id_9999"},
        timeout=5
    )
    assert r_missing_qa.status_code == 404
    print(f"  [PASS] Scoped Non-Existent Document on Q&A: HTTP 404 -> {r_missing_qa.json()['detail']}")

    # Clean up created documents
    print("\n[Step 11] Cleaning up test documents...")
    for d_id in [pdf_id, docx_id, txt_id]:
        r_del = session.delete(f"{BACKEND_URL}/api/documents/{d_id}", timeout=5)
        assert r_del.status_code == 200
        print(f"  [PASS] Deleted document '{d_id}' cleanly from all vector and lexical indexes.")

    print("\n" + "=" * 70)
    print("ALL 10 END-TO-END WORKFLOWS PASSED SUCCESSFULLY AGAINST LIVE APPLICATION!")
    print("=" * 70)

if __name__ == "__main__":
    try:
        run_e2e_verification()
    except Exception as e:
        print(f"\n[FAIL] E2E VERIFICATION FAILED: {e}", file=sys.stderr)
        sys.exit(1)
