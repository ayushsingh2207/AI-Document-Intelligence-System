import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.vector_store import vector_store
from app.schemas.document import DocumentPage

client = TestClient(app)


@pytest.fixture(autouse=True)
def cleanup_vector_store():
    """Ensure clean vector store state for tests."""
    vector_store.clear_all()
    yield
    vector_store.clear_all()


def _index_sample_contract(doc_id: str = "doc_contract_test") -> str:
    """Helper to index a multi-page legal agreement fixture."""
    page_1_text = (
        "THIS MASTER SERVICES AGREEMENT (the \"Agreement\") is entered into by and between "
        "Acme Global Technologies Inc., a Delaware corporation (\"Company\"), and "
        "Beta Services LLC, an Oregon limited liability company (\"Service Provider\"), "
        "effective as of January 15, 2024 (the \"Effective Date\").\n\n"
        "1. Services. Service Provider agrees to provide technical consulting services."
    )
    page_2_text = (
        "4. Term and Termination.\n"
        "This Agreement shall commence on the Effective Date and continue for a renewal term "
        "of one year. Either party may terminate for convenience upon thirty (30) days "
        "prior written notice to the other party.\n\n"
        "5. Governing Law.\n"
        "This Agreement shall be governed by and construed in accordance with the laws of the State of New York.\n\n"
        "6. Limitation of Liability.\n"
        "In no event shall aggregate liability exceed the total fees paid under this agreement. "
        "Neither party shall be subject to uncapped liability except for willful misconduct."
    )

    pages = [
        DocumentPage(
            page_number=1,
            text=page_1_text,
            char_count=len(page_1_text),
            word_count=len(page_1_text.split()),
            is_approximate=False,
            boundary_type="physical",
        ),
        DocumentPage(
            page_number=2,
            text=page_2_text,
            char_count=len(page_2_text),
            word_count=len(page_2_text.split()),
            is_approximate=False,
            boundary_type="physical",
        ),
    ]

    vector_store.index_document(
        doc_id=doc_id,
        filename="master_services_agreement.pdf",
        file_type="PDF",
        file_size_bytes=len(page_1_text) + len(page_2_text),
        pages=pages,
        chunk_size=400,
        chunk_overlap=50,
    )
    return doc_id


class TestContractIntelligenceAPI:
    """API endpoint and schema behavior tests for Phase 5.3."""

    def test_get_contract_categories(self):
        """Endpoint /api/documents/contract/categories returns all 41 CUAD categories."""
        response = client.get("/api/documents/contract/categories")
        assert response.status_code == 200
        categories = response.json()
        assert isinstance(categories, list)
        assert len(categories) == 41

        # Check key CUAD categories are included
        expected = [
            "Governing Law",
            "Termination For Convenience",
            "Cap On Liability",
            "Non-Compete",
            "Liquidated Damages",
            "Anti-Assignment",
            "Effective Date",
            "Parties",
        ]
        for exp in expected:
            assert exp in categories, f"Expected {exp} in 41 CUAD categories"

    def test_analyze_contract_success_with_detections(self):
        """Contract analysis accurately extracts clauses with page number and character offsets."""
        doc_id = _index_sample_contract("doc_contract_test")

        response = client.post(
            f"/api/documents/{doc_id}/contract-analysis",
            json={"confidence_threshold": 3.0},
        )
        assert response.status_code == 200
        data = response.json()

        assert data["doc_id"] == doc_id
        assert data["filename"] == "master_services_agreement.pdf"
        assert data["total_pages"] == 2
        assert data["categories_analyzed"] == 41
        assert data["clauses_detected_count"] > 0
        assert data["clauses_not_detected_count"] > 0
        assert "ACADEMIC DEMONSTRATION ONLY" in data["disclaimer"]

        # Inspect specific detected categories
        results_by_cat = {r["category"]: r for r in data["results"]}

        # 1. Governing Law
        gov_law = results_by_cat.get("Governing Law")
        assert gov_law is not None
        assert gov_law["detected"] is True
        assert gov_law["detection_status"] == "detected"
        assert gov_law["page_number"] == 2
        assert "governed by" in gov_law["extracted_text"].lower()
        assert gov_law["confidence_score"] >= 3.0
        assert gov_law["start_char"] is not None
        assert gov_law["end_char"] is not None
        assert gov_law["start_char"] < gov_law["end_char"]

        # 2. Termination For Convenience
        term_conv = results_by_cat.get("Termination For Convenience")
        assert term_conv is not None
        assert term_conv["detected"] is True
        assert "terminate for convenience" in term_conv["extracted_text"].lower()
        assert term_conv["page_number"] == 2

        # 3. Cap On Liability
        cap_liab = results_by_cat.get("Cap On Liability")
        assert cap_liab is not None
        assert cap_liab["detected"] is True
        assert "liability" in cap_liab["extracted_text"].lower()

    def test_analyze_contract_distinguishes_no_detection_from_absence(self):
        """Categories without trigger matches are reported as not detected, not absent."""
        doc_id = _index_sample_contract("doc_contract_test")

        response = client.post(f"/api/documents/{doc_id}/contract-analysis", json={})
        assert response.status_code == 200
        data = response.json()

        results_by_cat = {r["category"]: r for r in data["results"]}

        # Liquidated damages is NOT present in the sample contract
        liq_damages = results_by_cat.get("Liquidated Damages")
        assert liq_damages is not None
        assert liq_damages["detected"] is False
        assert liq_damages["detection_status"] == "not_detected"
        assert liq_damages["extracted_text"] is None
        assert liq_damages["page_number"] is None
        assert liq_damages["start_char"] is None
        assert liq_damages["end_char"] is None
        assert liq_damages["confidence_score"] == 0.0
        # Crucial requirement: Must distinguish no detection from verified absence
        assert "Not detected" in liq_damages["explanation"]
        assert "does not verify legal absence" in liq_damages["explanation"]

    def test_analyze_contract_category_subset(self):
        """User can optionally scope analysis to a subset of categories."""
        doc_id = _index_sample_contract("doc_contract_test")

        response = client.post(
            f"/api/documents/{doc_id}/contract-analysis",
            json={
                "categories": ["Governing Law", "Liquidated Damages"],
                "confidence_threshold": 3.0,
            },
        )
        assert response.status_code == 200
        data = response.json()

        assert data["categories_analyzed"] == 2
        assert len(data["results"]) == 2
        cats = [r["category"] for r in data["results"]]
        assert "Governing Law" in cats
        assert "Liquidated Damages" in cats

    def test_analyze_contract_document_isolation(self):
        """Analysis is isolated to the specified document ID."""
        doc_a = _index_sample_contract("doc_contract_a")

        # Index separate doc B with different text
        page_b = DocumentPage(
            page_number=1,
            text="This is an unrelated purchase order with no special clauses.",
            char_count=58,
            word_count=10,
        )
        vector_store.index_document(
            doc_id="doc_contract_b",
            filename="purchase_order.txt",
            file_type="TXT",
            file_size_bytes=58,
            pages=[page_b],
            chunk_size=300,
            chunk_overlap=0,
        )

        response_b = client.post("/api/documents/doc_contract_b/contract-analysis", json={})
        assert response_b.status_code == 200
        data_b = response_b.json()
        assert data_b["doc_id"] == "doc_contract_b"
        assert data_b["filename"] == "purchase_order.txt"
        assert data_b["clauses_detected_count"] == 0

    def test_analyze_contract_nonexistent_document(self):
        """Requesting an unindexed document ID returns 404 Not Found."""
        response = client.post("/api/documents/doc_does_not_exist/contract-analysis", json={})
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    def test_analyze_contract_empty_document(self):
        """An indexed document with no text chunks gracefully returns 0 detections."""
        empty_page = DocumentPage(
            page_number=1,
            text="",
            char_count=0,
            word_count=0,
        )
        vector_store.index_document(
            doc_id="doc_empty",
            filename="blank.pdf",
            file_type="PDF",
            file_size_bytes=0,
            pages=[empty_page],
        )

        response = client.post("/api/documents/doc_empty/contract-analysis", json={})
        assert response.status_code == 200
        data = response.json()
        assert data["doc_id"] == "doc_empty"
        assert data["total_chunks_scanned"] == 0
        assert data["clauses_detected_count"] == 0
        assert data["clauses_not_detected_count"] == 41
        assert all(r["detected"] is False for r in data["results"])

    def test_analyze_contract_whitespace_doc_id(self):
        """Whitespace document ID returns 400 Bad Request."""
        response = client.post("/api/documents/%20%20%20/contract-analysis", json={})
        assert response.status_code == 400
        assert "empty or contain only whitespace" in response.json()["detail"]
