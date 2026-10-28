import io
import pytest
from fastapi.testclient import TestClient
from app.services.chunker import chunk_page_text, chunk_document_pages
from app.services.embedding_service import embedding_service
from app.services.vector_store import vector_store
from app.schemas.document import DocumentPage

@pytest.fixture(autouse=True)
def clean_vector_store():
    """Ensure clean vector store state before and after each test."""
    vector_store.clear_all()
    yield
    vector_store.clear_all()

def test_semantic_chunker_boundaries_and_offsets():
    text = (
        "Artificial Intelligence represents a major paradigm shift in computer science.\n\n"
        "Natural Language Processing allows machines to comprehend human syntax and semantics. "
        "Dense retrieval maps queries and passages into a shared vector representation space."
    )
    chunks = chunk_page_text(text, chunk_size=120, chunk_overlap=30)
    assert len(chunks) >= 2
    
    for c_text, start, end in chunks:
        assert len(c_text) > 0
        # Exact character offset verification
        assert text[start:end].strip() == c_text

def test_chunk_document_pages_metadata_preservation():
    pages = [
        DocumentPage(
            page_number=1,
            text="First page introduces vector embeddings and dense retrieval concepts.",
            char_count=67,
            word_count=9,
            boundary_type="physical",
            is_approximate=False
        ),
        DocumentPage(
            page_number=2,
            text="Second page covers approximate nearest neighbors and FAISS index construction.",
            char_count=77,
            word_count=10,
            boundary_type="physical",
            is_approximate=False
        )
    ]
    records = chunk_document_pages("doc_123", "guide.pdf", pages, chunk_size=200, chunk_overlap=20)
    assert len(records) >= 2
    
    # Check page attribution
    assert records[0].page_number == 1
    assert records[0].boundary_type == "physical"
    assert records[0].is_approximate is False
    assert records[0].chunk_id == "doc_123_p1_c0"
    assert records[0].start_char >= 0
    assert records[0].end_char > records[0].start_char

    # Verify second page record
    p2_record = next(r for r in records if r.page_number == 2)
    assert p2_record.page_number == 2
    assert p2_record.boundary_type == "physical"
    assert "FAISS" in p2_record.text

def test_embedding_dimensions_and_normalization():
    info = embedding_service.get_model_info()
    assert info["dimension"] == 384
    assert info["license"] == "Apache-2.0"

    texts = [
        "Financial regulatory disclosure document.",
        "Convolutional neural networks for computer vision."
    ]
    vectors = embedding_service.embed_texts(texts)
    assert vectors.shape == (2, 384)
    assert vectors.dtype.name == "float32"

    # Verify L2 unit normalization (norm approx 1.0)
    norm0 = (vectors[0] ** 2).sum() ** 0.5
    assert pytest.approx(norm0, 1e-4) == 1.0

def test_semantic_ranking_synthetic_passages():
    """Verify semantic similarity correctly ranks relevant passage above distractors."""
    query = "What are the rules regarding contract termination and cancellation notice?"
    
    doc1_text = "Section 9: The agreement may be terminated by either party with thirty days written notice."
    doc2_text = "Section 2: Coffee and tea refreshments are provided in the main cafeteria on weekdays."
    doc3_text = "Section 5: Annual employee performance reviews take place during the third quarter."

    pages = [
        DocumentPage(page_number=1, text=doc1_text, char_count=len(doc1_text), word_count=len(doc1_text.split())),
        DocumentPage(page_number=2, text=doc2_text, char_count=len(doc2_text), word_count=len(doc2_text.split())),
        DocumentPage(page_number=3, text=doc3_text, char_count=len(doc3_text), word_count=len(doc3_text.split())),
    ]

    vector_store.index_document(
        doc_id="policy_doc",
        filename="company_policy.txt",
        file_type="TXT",
        file_size_bytes=len(doc1_text) + len(doc2_text) + len(doc3_text),
        pages=pages
    )

    search_resp = vector_store.search(query=query, top_k=3)
    assert search_resp.total_results >= 1
    top_result = search_resp.results[0]
    
    # Top result must be page 1 (contract termination)
    assert top_result.page_number == 1
    assert "terminated" in top_result.text.lower()
    assert top_result.score > 0.4
    
    # Page 1 score should be significantly higher than cafeteria refreshments
    if len(search_resp.results) > 1:
        assert top_result.score > search_resp.results[-1].score

def test_api_multi_document_indexing_and_search(client: TestClient):
    # Upload Document A
    doc_a_content = "Document A discusses quantum computing, qubits, and quantum entanglement principles."
    client.post(
        "/api/documents/upload",
        files={"file": ("quantum_guide.txt", doc_a_content.encode("utf-8"), "text/plain")}
    )

    # Upload Document B
    doc_b_content = "Document B discusses sustainable agriculture, soil biology, and organic crop rotation."
    client.post(
        "/api/documents/upload",
        files={"file": ("agriculture_manual.txt", doc_b_content.encode("utf-8"), "text/plain")}
    )

    # Search for quantum topic
    search_q = client.post("/api/documents/search", json={"query": "superposition and qubits in quantum processors", "top_k": 3})
    assert search_q.status_code == 200
    res_data = search_q.json()
    assert res_data["total_results"] >= 1
    assert "quantum_guide.txt" in res_data["results"][0]["filename"]

    # Search for farming topic
    search_f = client.post("/api/documents/search", json={"query": "organic soil fertility and crops", "top_k": 3})
    assert search_f.status_code == 200
    res_f = search_f.json()
    assert res_f["total_results"] >= 1
    assert "agriculture_manual.txt" in res_f["results"][0]["filename"]

def test_duplicate_upload_updates_index_without_stale_vectors(client: TestClient):
    filename = "terms_of_service.txt"
    initial_content = "Version 1.0 of the terms and conditions."
    client.post("/api/documents/upload", files={"file": (filename, initial_content.encode("utf-8"), "text/plain")})
    
    stats1 = client.get("/api/documents/index/stats").json()
    initial_chunks = stats1["total_chunks"]
    assert initial_chunks >= 1

    # Re-upload updated version of the same document
    updated_content = "Version 2.0 with revised privacy policy and security protocols."
    client.post("/api/documents/upload", files={"file": (filename, updated_content.encode("utf-8"), "text/plain")})

    stats2 = client.get("/api/documents/index/stats").json()
    # Number of documents in index must still be 1 (deduplicated)
    assert stats2["total_documents"] == 1
    assert stats2["total_vectors"] == stats2["total_chunks"]

    # Search should find Version 2.0
    search_res = client.post("/api/documents/search", json={"query": "privacy policy protocols", "top_k": 2}).json()
    assert "Version 2.0" in search_res["results"][0]["text"]

def test_document_deletion_purges_index(client: TestClient):
    content = "Sensitive classified intelligence data."
    up_res = client.post("/api/documents/upload", files={"file": ("classified.txt", content.encode("utf-8"), "text/plain")}).json()
    doc_id = up_res["doc_id"]
    assert doc_id is not None

    # Verify searchable
    s1 = client.post("/api/documents/search", json={"query": "classified intelligence", "top_k": 1}).json()
    assert s1["total_results"] == 1

    # Delete document
    del_res = client.delete(f"/api/documents/{doc_id}")
    assert del_res.status_code == 200
    assert del_res.json()["success"] is True

    # Search again - must yield 0 results
    s2 = client.post("/api/documents/search", json={"query": "classified intelligence", "top_k": 1}).json()
    assert s2["total_results"] == 0

def test_empty_text_and_empty_index_graceful_handling(client: TestClient):
    # Empty index search
    res = client.post("/api/documents/search", json={"query": "anything", "top_k": 5})
    assert res.status_code == 200
    data = res.json()
    assert data["total_results"] == 0
    assert "empty" in data["message"].lower()

def test_index_stats_endpoint(client: TestClient):
    res = client.get("/api/documents/index/stats")
    assert res.status_code == 200
    stats = res.json()
    assert stats["dimension"] == 384
    assert "all-MiniLM-L6-v2" in stats["embedding_model"]
    assert stats["model_license"] == "Apache-2.0"
    assert "FAISS" in stats["index_type"]
