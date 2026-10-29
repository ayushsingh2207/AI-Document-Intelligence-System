"""
Phase 5.1 Tests: Grounded Q&A Backend
======================================
Tests for:
1. Evidence-supported answering with verifiable source citations and character offsets.
2. Conservative abstention on absent, out-of-domain, or insufficient evidence.
3. Document scope enforcement (scoped queries never cite other documents).
4. Multi-document evidence attribution when unscoped.
5. Error handling for empty queries, whitespace, invalid doc_ids, and empty index.
6. Zero regression on existing Phase 1-3 hybrid search endpoints.
"""

import pytest
import os
import json
import tempfile
from fastapi.testclient import TestClient
from app.main import app
from app.services.vector_store import VectorStore
from app.services.bm25_store import BM25Store
from app.services.hybrid_retriever import HybridRetriever
from app.services.grounded_qa import GroundedQAService
from app.schemas.document import DocumentPage
from app.schemas.qa import QARequest, QAResponse


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def isolated_qa_env():
    """
    Creates an isolated VectorStore, BM25Store, and GroundedQAService in a temp directory
    so test cases do not pollute the production data directory.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        v_store = VectorStore(dimension=384, data_dir=tmp_dir)
        b_store = BM25Store(data_dir=tmp_dir)
        h_retriever = HybridRetriever(vector_store=v_store, bm25_store=b_store)
        qa_service = GroundedQAService(hybrid_retriever=h_retriever, vector_store=v_store)
        yield {
            "v_store": v_store,
            "b_store": b_store,
            "h_retriever": h_retriever,
            "qa_service": qa_service,
            "tmp_dir": tmp_dir,
        }


# ─── Service-Level Unit Tests ──────────────────────────────────────────

class TestGroundedQAService:
    def test_qa_supported_answer_with_valid_citations(self, isolated_qa_env):
        """Verify that an answerable question returns the source sentence and exact citation offsets."""
        v_store = isolated_qa_env["v_store"]
        qa_service = isolated_qa_env["qa_service"]

        page_text = (
            "Section 4. Warranties and Maintenance. "
            "Accuray warrants that all replacement parts shall be free from defects for a period of ninety (90) days from shipment. "
            "The customer must notify Accuray in writing within ten days of discovering any defect."
        )
        page = DocumentPage(
            page_number=1,
            text=page_text,
            char_count=len(page_text),
            word_count=len(page_text.split()),
            boundary_type="physical",
            is_approximate=False,
        )

        v_store.index_document(
            doc_id="doc_warranty_001",
            filename="Accuray_Distributor_Agreement.pdf",
            file_type="PDF",
            file_size_bytes=len(page_text.encode()),
            pages=[page],
            chunk_size=400,
            chunk_overlap=50,
        )

        req = QARequest(
            question="What is the warranty period for replacement parts?",
            doc_id="doc_warranty_001",
            top_k=3,
            confidence_threshold=0.45,
        )
        resp: QAResponse = qa_service.answer_question(req)

        assert resp.answered is True
        assert resp.confidence >= 0.45
        assert "ninety (90) days" in resp.answer
        assert len(resp.citations) >= 1

        citation = resp.citations[0]
        assert citation.doc_id == "doc_warranty_001"
        assert citation.filename == "Accuray_Distributor_Agreement.pdf"
        assert citation.page_number == 1
        assert "ninety (90) days from shipment" in citation.supporting_excerpt
        # Verify character offsets point to exact text in the source page
        extracted_from_page = page_text[citation.start_char:citation.end_char]
        assert extracted_from_page == citation.supporting_excerpt

    def test_qa_conservative_abstention_on_absent_fact(self, isolated_qa_env):
        """Verify that when evidence is absent, the system conservatively abstains with zero citations."""
        v_store = isolated_qa_env["v_store"]
        qa_service = isolated_qa_env["qa_service"]

        page_text = (
            "This Agreement is entered into by and between Alpha Corp and Beta LLC. "
            "This Agreement shall be governed by the laws of the State of New York."
        )
        page = DocumentPage(
            page_number=1,
            text=page_text,
            char_count=len(page_text),
            word_count=len(page_text.split()),
            boundary_type="physical",
            is_approximate=False,
        )

        v_store.index_document(
            doc_id="doc_alpha_001",
            filename="Alpha_Contract.pdf",
            file_type="PDF",
            file_size_bytes=len(page_text.encode()),
            pages=[page],
        )

        # Question about early termination penalty, which does not exist in the contract
        req = QARequest(
            question="What is the liquidated damages penalty for early termination?",
            doc_id="doc_alpha_001",
            confidence_threshold=0.45,
        )
        resp: QAResponse = qa_service.answer_question(req)

        assert resp.answered is False
        assert resp.abstention_reason == "insufficient_evidence"
        assert "could not find sufficient evidence" in resp.answer
        assert len(resp.citations) == 0  # No fabricated citations allowed

    def test_qa_conservative_abstention_on_out_of_domain_query(self, isolated_qa_env):
        """Verify system abstains on completely irrelevant questions."""
        v_store = isolated_qa_env["v_store"]
        qa_service = isolated_qa_env["qa_service"]

        page_text = "The quick brown fox jumps over the lazy dog in the sunny park."
        page = DocumentPage(
            page_number=1,
            text=page_text,
            char_count=len(page_text),
            word_count=len(page_text.split()),
        )

        v_store.index_document(
            doc_id="doc_fox_001",
            filename="Fox_Story.txt",
            file_type="TXT",
            file_size_bytes=len(page_text.encode()),
            pages=[page],
        )

        req = QARequest(
            question="What is the boiling point of liquid nitrogen at 1 atmosphere?",
            confidence_threshold=0.45,
        )
        resp = qa_service.answer_question(req)

        assert resp.answered is False
        assert resp.abstention_reason == "insufficient_evidence"
        assert len(resp.citations) == 0

    def test_qa_document_scope_strict_enforcement(self, isolated_qa_env):
        """Verify that scoping a query to doc A never cites doc B even if doc B has higher match."""
        v_store = isolated_qa_env["v_store"]
        qa_service = isolated_qa_env["qa_service"]

        # Doc A has general terms
        doc_a_text = "Alpha Corp provides professional cloud consulting services under Standard Rate Schedule A."
        page_a = DocumentPage(page_number=1, text=doc_a_text, char_count=len(doc_a_text), word_count=len(doc_a_text.split()))
        v_store.index_document(doc_id="doc_A", filename="Alpha_Doc.pdf", file_type="PDF", file_size_bytes=len(doc_a_text.encode()), pages=[page_a])

        # Doc B has governing law
        doc_b_text = "This Agreement shall be governed exclusively by the laws of California without regard to conflict principles."
        page_b = DocumentPage(page_number=2, text=doc_b_text, char_count=len(doc_b_text), word_count=len(doc_b_text.split()))
        v_store.index_document(doc_id="doc_B", filename="Beta_Doc.pdf", file_type="PDF", file_size_bytes=len(doc_b_text.encode()), pages=[page_b])

        # Query about governing law scoped to Doc A (where it is absent)
        req_a = QARequest(
            question="Which state laws govern the agreement?",
            doc_id="doc_A",
            confidence_threshold=0.45,
        )
        resp_a = qa_service.answer_question(req_a)

        # Must abstain because Doc A does not have governing law
        assert resp_a.answered is False
        for cit in resp_a.citations:
            assert cit.doc_id == "doc_A"

        # Now query scoped to Doc B
        req_b = QARequest(
            question="Which state laws govern the agreement?",
            doc_id="doc_B",
            confidence_threshold=0.45,
        )
        resp_b = qa_service.answer_question(req_b)

        assert resp_b.answered is True
        assert "California" in resp_b.answer
        assert all(cit.doc_id == "doc_B" for cit in resp_b.citations)

    def test_qa_multi_document_unscoped_evidence(self, isolated_qa_env):
        """Verify that an unscoped query can cite relevant evidence across multiple documents."""
        v_store = isolated_qa_env["v_store"]
        qa_service = isolated_qa_env["qa_service"]

        doc_1 = "The primary project lead for Architecture Design is Dr. Alice Walker."
        p1 = DocumentPage(page_number=1, text=doc_1, char_count=len(doc_1), word_count=len(doc_1.split()))
        v_store.index_document(doc_id="doc_1", filename="Project_Charter.pdf", file_type="PDF", file_size_bytes=len(doc_1.encode()), pages=[p1])

        doc_2 = "The lead software engineer for Backend Services is Robert Martinez."
        p2 = DocumentPage(page_number=1, text=doc_2, char_count=len(doc_2), word_count=len(doc_2.split()))
        v_store.index_document(doc_id="doc_2", filename="Staffing_Plan.pdf", file_type="PDF", file_size_bytes=len(doc_2.encode()), pages=[p2])

        req = QARequest(
            question="Who is the lead for Architecture Design?",
            doc_id=None,  # unscoped
            confidence_threshold=0.45,
        )
        resp = qa_service.answer_question(req)

        assert resp.answered is True
        assert "Alice Walker" in resp.answer
        assert resp.citations[0].doc_id == "doc_1"
        assert resp.citations[0].filename == "Project_Charter.pdf"

    def test_qa_empty_index_behavior(self, isolated_qa_env):
        """Verify clean handling when no documents exist."""
        qa_service = isolated_qa_env["qa_service"]
        req = QARequest(question="Who is the primary contractor?")
        resp = qa_service.answer_question(req)

        assert resp.answered is False
        assert resp.abstention_reason == "index_empty"
        assert "No documents have been indexed yet" in resp.answer
        assert resp.citations == []


# ─── FastAPI Endpoint Integration Tests ─────────────────────────────────

class TestQAEndpointIntegration:
    def test_post_qa_endpoint_success(self, client):
        """Test POST /api/documents/qa with valid request against existing test documents."""
        # 1. Upload a test document to ensure index has content
        test_content = (
            "CONFIDENTIAL SERVICES AGREEMENT. "
            "The initial term of this Agreement shall commence on October 1, 2024 and expire on September 30, 2027. "
            "Either party may terminate upon sixty (60) days prior written notice."
        )
        upload_resp = client.post(
            "/api/documents/upload",
            files={"file": ("QA_Test_Contract.txt", test_content.encode("utf-8"), "text/plain")},
        )
        assert upload_resp.status_code == 200
        doc_id = upload_resp.json()["doc_id"]

        # 2. Ask question
        qa_payload = {
            "question": "What is the expiration date of the agreement?",
            "doc_id": doc_id,
            "top_k": 3,
            "confidence_threshold": 0.40,
        }
        res = client.post("/api/documents/qa", json=qa_payload)
        assert res.status_code == 200
        data = res.json()

        assert data["answered"] is True
        assert "September 30, 2027" in data["answer"]
        assert len(data["citations"]) >= 1
        assert data["citations"][0]["doc_id"] == doc_id
        assert data["citations"][0]["filename"] == "QA_Test_Contract.txt"
        assert data["citations"][0]["page_number"] == 1
        assert data["confidence"] >= 0.40
        assert data["latency_ms"] >= 0.0

        # Clean up
        client.delete(f"/api/documents/{doc_id}")

    def test_post_qa_endpoint_abstention(self, client):
        """Test POST /api/documents/qa returns answered=False when question is absent."""
        test_content = "This document only contains details regarding employee parking permits in lot B."
        upload_resp = client.post(
            "/api/documents/upload",
            files={"file": ("Parking_Policy.txt", test_content.encode("utf-8"), "text/plain")},
        )
        assert upload_resp.status_code == 200
        doc_id = upload_resp.json()["doc_id"]

        qa_payload = {
            "question": "What are the intellectual property licensing royalties?",
            "doc_id": doc_id,
            "confidence_threshold": 0.45,
        }
        res = client.post("/api/documents/qa", json=qa_payload)
        assert res.status_code == 200
        data = res.json()

        assert data["answered"] is False
        assert data["abstention_reason"] == "insufficient_evidence"
        assert data["citations"] == []

        client.delete(f"/api/documents/{doc_id}")

    def test_post_qa_invalid_doc_id_404(self, client):
        """Test POST /api/documents/qa with nonexistent doc_id returns 404."""
        qa_payload = {
            "question": "What is the term?",
            "doc_id": "doc_nonexistent_99999",
        }
        res = client.post("/api/documents/qa", json=qa_payload)
        assert res.status_code == 404
        assert "not found" in res.json()["detail"].lower()

    def test_post_qa_empty_and_whitespace_validation(self, client):
        """Test validation error for empty or whitespace-only questions."""
        # Pydantic schema min_length=1 rejects empty string with 422
        res1 = client.post("/api/documents/qa", json={"question": ""})
        assert res1.status_code == 422

        # Whitespace-only string rejected by router check with 400
        res2 = client.post("/api/documents/qa", json={"question": "    "})
        assert res2.status_code == 400
        assert "whitespace" in res2.json()["detail"].lower()

    def test_no_regression_in_search_endpoints(self, client):
        """Verify that existing POST and GET /api/documents/search endpoints remain unchanged."""
        test_content = "The governing law shall be Delaware corporate law for all transactions."
        upload_resp = client.post(
            "/api/documents/upload",
            files={"file": ("Delaware_Law.txt", test_content.encode("utf-8"), "text/plain")},
        )
        assert upload_resp.status_code == 200
        doc_id = upload_resp.json()["doc_id"]

        # POST /search
        search_post = client.post(
            "/api/documents/search",
            json={"query": "Delaware corporate law", "top_k": 3, "strategy": "hybrid"},
        )
        assert search_post.status_code == 200
        post_data = search_post.json()
        assert post_data["total_results"] >= 1
        assert post_data["retrieval_strategy"] == "hybrid"
        assert "results" in post_data

        # GET /search
        search_get = client.get("/api/documents/search?q=Delaware+corporate+law&strategy=hybrid")
        assert search_get.status_code == 200
        get_data = search_get.json()
        assert get_data["total_results"] >= 1

        client.delete(f"/api/documents/{doc_id}")
