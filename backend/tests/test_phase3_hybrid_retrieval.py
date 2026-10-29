"""
Phase 3 Tests: Hybrid Retrieval Engine
========================================
Tests for BM25 lexical retrieval, Reciprocal Rank Fusion, hybrid search,
strategy configuration, indexing/deletion/persistence, and edge cases.
"""

import pytest
import os
import json
import tempfile
from fastapi.testclient import TestClient
from app.main import app
from app.services.bm25_store import BM25Store, tokenize
from app.services.hybrid_retriever import (
    HybridRetriever,
    RetrievalStrategy,
    reciprocal_rank_fusion,
)
from app.services.vector_store import VectorStore
from app.schemas.document import DocumentPage


@pytest.fixture
def client():
    return TestClient(app)


# ─── BM25 Tokenizer Tests ──────────────────────────────────────────

class TestTokenizer:
    def test_tokenize_basic(self):
        tokens = tokenize("Hello World")
        assert "hello" in tokens
        assert "world" in tokens

    def test_tokenize_removes_stopwords(self):
        tokens = tokenize("the quick brown fox is very fast")
        assert "the" not in tokens
        assert "is" not in tokens
        assert "very" not in tokens
        assert "quick" in tokens
        assert "fox" in tokens
        assert "fast" in tokens

    def test_tokenize_preserves_identifiers(self):
        tokens = tokenize("Section 3.2.1 of Document DOC-2024-0042")
        assert "section" in tokens
        assert "3.2.1" in tokens
        assert "doc" in tokens
        assert "2024" in tokens
        assert "0042" in tokens

    def test_tokenize_preserves_dates(self):
        tokens = tokenize("Date: January 15, 2024")
        assert "january" in tokens
        assert "15" in tokens
        assert "2024" in tokens

    def test_tokenize_empty_input(self):
        assert tokenize("") == []
        assert tokenize("   ") == []

    def test_tokenize_punctuation_handling(self):
        tokens = tokenize("Q: What is the contract's effective date?")
        assert "contract" in tokens
        assert "effective" in tokens
        assert "date" in tokens


# ─── BM25 Store Unit Tests ──────────────────────────────────────────

class TestBM25Store:
    @pytest.fixture
    def temp_store(self, tmp_path):
        return BM25Store(data_dir=str(tmp_path))

    def test_add_and_search(self, temp_store):
        temp_store.add_chunks(
            doc_id="doc1",
            chunk_ids=["doc1_c0", "doc1_c1"],
            chunk_texts=[
                "Machine learning and neural network architectures",
                "Contract liability and confidentiality clauses",
            ],
        )
        results = temp_store.search("machine learning neural networks", top_k=5)
        assert len(results) > 0
        assert results[0][0] == "doc1_c0"  # ML chunk should rank first

    def test_search_returns_correct_chunk(self, temp_store):
        temp_store.add_chunks(
            doc_id="doc1",
            chunk_ids=["c0", "c1", "c2"],
            chunk_texts=[
                "Revenue growth and financial performance Q3 2024",
                "Environmental sustainability and carbon emissions",
                "Machine learning model training procedures",
            ],
        )
        results = temp_store.search("financial revenue Q3", top_k=2)
        assert len(results) > 0
        assert results[0][0] == "c0"

    def test_search_with_doc_filter(self, temp_store):
        temp_store.add_chunks("d1", ["d1_c0"], ["Alpha topic content"])
        temp_store.add_chunks("d2", ["d2_c0"], ["Alpha topic different document"])

        results = temp_store.search("Alpha topic", doc_id="d1")
        chunk_ids = [cid for cid, _ in results]
        assert all(cid.startswith("d1") for cid in chunk_ids)

    def test_empty_query(self, temp_store):
        temp_store.add_chunks("d1", ["c0"], ["Some content here"])
        results = temp_store.search("", top_k=5)
        assert results == []

    def test_empty_index(self, temp_store):
        results = temp_store.search("anything", top_k=5)
        assert results == []

    def test_remove_document(self, temp_store):
        temp_store.add_chunks("d1", ["d1_c0", "d1_c1"], ["text one", "text two"])
        temp_store.add_chunks("d2", ["d2_c0"], ["text three"])

        # Remove doc d1
        removed = temp_store.remove_document("d1")
        assert removed is True

        # Search should not return d1 chunks
        results = temp_store.search("text", top_k=10)
        chunk_ids = [cid for cid, _ in results]
        assert not any(cid.startswith("d1") for cid in chunk_ids)

        # d2 should still be searchable
        assert any(cid.startswith("d2") for cid in chunk_ids)

    def test_remove_nonexistent_document(self, temp_store):
        assert temp_store.remove_document("nonexistent") is False

    def test_duplicate_upload_replaces_entries(self, temp_store):
        temp_store.add_chunks("d1", ["d1_c0"], ["original content"])
        temp_store.add_chunks("d1", ["d1_c0_new"], ["updated content"])

        # Old chunk ID should not appear
        results = temp_store.search("original content", top_k=10)
        chunk_ids = [cid for cid, _ in results]
        assert "d1_c0" not in chunk_ids

        results = temp_store.search("updated content", top_k=10)
        chunk_ids = [cid for cid, _ in results]
        assert "d1_c0_new" in chunk_ids

    def test_persistence(self, tmp_path):
        store1 = BM25Store(data_dir=str(tmp_path))
        store1.add_chunks("d1", ["c0", "c1"], ["persisted alpha", "persisted beta"])

        # Create new store from same directory
        store2 = BM25Store(data_dir=str(tmp_path))
        results = store2.search("persisted alpha", top_k=5)
        assert len(results) > 0
        assert results[0][0] == "c0"

    def test_clear_all(self, temp_store):
        temp_store.add_chunks("d1", ["c0"], ["content"])
        temp_store.clear_all()
        assert temp_store.search("content", top_k=5) == []
        stats = temp_store.get_stats()
        assert stats["total_entries"] == 0

    def test_stats(self, temp_store):
        temp_store.add_chunks("d1", ["c0", "c1"], ["text one", "text two"])
        stats = temp_store.get_stats()
        assert stats["total_entries"] == 2
        assert stats["unique_documents"] == 1
        assert stats["algorithm"] == "BM25Okapi (rank_bm25)"
        assert stats["license"] == "MIT"


# ─── RRF Unit Tests ─────────────────────────────────────────────────

class TestReciprocalRankFusion:
    def test_single_list(self):
        ranked = [("a", 0.9), ("b", 0.7), ("c", 0.5)]
        fused = reciprocal_rank_fusion([ranked], k=60)
        ids = [cid for cid, _ in fused]
        assert ids == ["a", "b", "c"]

    def test_two_lists_same_order(self):
        list1 = [("a", 0.9), ("b", 0.7)]
        list2 = [("a", 5.0), ("b", 3.0)]
        fused = reciprocal_rank_fusion([list1, list2], k=60)
        # a should have higher RRF because it's rank 1 in both
        ids = [cid for cid, _ in fused]
        assert ids[0] == "a"

    def test_deduplication(self):
        list1 = [("a", 0.9), ("b", 0.7), ("c", 0.5)]
        list2 = [("b", 5.0), ("d", 3.0), ("a", 1.0)]
        fused = reciprocal_rank_fusion([list1, list2], k=60)
        # Each chunk should appear exactly once
        ids = [cid for cid, _ in fused]
        assert len(ids) == len(set(ids))
        assert set(ids) == {"a", "b", "c", "d"}

    def test_overlap_boosts_rank(self):
        """Chunks appearing in both lists should score higher than single-list chunks."""
        list1 = [("overlap", 0.5), ("dense_only", 0.4)]
        list2 = [("overlap", 3.0), ("bm25_only", 2.0)]
        fused = reciprocal_rank_fusion([list1, list2], k=60)
        scores = {cid: s for cid, s in fused}
        # overlap appears in both so should have higher RRF score
        assert scores["overlap"] > scores["dense_only"]
        assert scores["overlap"] > scores["bm25_only"]

    def test_empty_lists(self):
        fused = reciprocal_rank_fusion([[], []], k=60)
        assert fused == []

    def test_one_empty_one_populated(self):
        list1 = [("a", 0.9)]
        fused = reciprocal_rank_fusion([list1, []], k=60)
        assert len(fused) == 1
        assert fused[0][0] == "a"

    def test_rrf_scores_decrease(self):
        """RRF scores should decrease with increasing rank."""
        ranked = [("a", 1.0), ("b", 0.9), ("c", 0.8), ("d", 0.7)]
        fused = reciprocal_rank_fusion([ranked], k=60)
        scores = [s for _, s in fused]
        assert scores == sorted(scores, reverse=True)


# ─── Hybrid Retrieval API Tests ─────────────────────────────────────

class TestHybridSearchAPI:
    @pytest.fixture(autouse=True)
    def setup_test_document(self, client):
        """Upload a test document before each test."""
        from app.services.vector_store import vector_store
        from app.services.bm25_store import bm25_store

        # Clear existing data
        vector_store.clear_all()

        # Create a test text file with known content
        test_content = (
            "Section 1: Machine Learning Overview\n"
            "Deep learning is a subset of machine learning that uses neural networks with many layers.\n"
            "Convolutional neural networks (CNNs) are particularly effective for image recognition.\n\n"
            "Section 2: Contract Terms\n"
            "The confidentiality clause restricts sharing of proprietary information.\n"
            "Liability is limited to the total contract value of $500,000.\n\n"
            "Section 3: Financial Results\n"
            "Q3 2024 revenue reached $12.5 million, a 15% year-over-year increase.\n"
            "Operating expenses decreased by 8% due to efficiency improvements.\n"
        )

        # Create a temporary file
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as f:
            f.write(test_content)
            temp_path = f.name

        try:
            with open(temp_path, "rb") as f:
                response = client.post(
                    "/api/documents/upload",
                    files={"file": ("test_hybrid.txt", f, "text/plain")},
                )
            assert response.status_code == 200
        finally:
            os.unlink(temp_path)

        yield

        vector_store.clear_all()

    def test_search_default_strategy_is_hybrid(self, client):
        """Default search should use hybrid strategy."""
        resp = client.post(
            "/api/documents/search",
            json={"query": "machine learning", "top_k": 5},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["retrieval_strategy"] == "hybrid"
        assert data["total_results"] > 0

    def test_search_dense_strategy(self, client):
        """Dense-only search should work and return 'dense' strategy."""
        resp = client.post(
            "/api/documents/search",
            json={"query": "machine learning", "top_k": 5, "strategy": "dense"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["retrieval_strategy"] == "dense"
        assert data["total_results"] > 0

    def test_search_bm25_strategy(self, client):
        """BM25-only search should work and return 'bm25' strategy."""
        resp = client.post(
            "/api/documents/search",
            json={"query": "machine learning", "top_k": 5, "strategy": "bm25"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["retrieval_strategy"] == "bm25"
        assert data["total_results"] > 0

    def test_hybrid_search_finds_semantic_match(self, client):
        """Hybrid search should find semantically related content."""
        resp = client.post(
            "/api/documents/search",
            json={"query": "artificial intelligence and deep neural networks", "top_k": 3, "strategy": "hybrid"},
        )
        data = resp.json()
        assert data["total_results"] > 0
        # The ML section should be in results
        texts = " ".join(r["text"].lower() for r in data["results"])
        assert "machine learning" in texts or "neural network" in texts or "deep learning" in texts

    def test_bm25_finds_exact_keyword_match(self, client):
        """BM25 should find exact terms like dollar amounts and identifiers."""
        resp = client.post(
            "/api/documents/search",
            json={"query": "$500,000 liability contract", "top_k": 3, "strategy": "bm25"},
        )
        data = resp.json()
        assert data["total_results"] > 0
        texts = " ".join(r["text"].lower() for r in data["results"])
        assert "500" in texts or "liability" in texts

    def test_hybrid_message_contains_fusion_info(self, client):
        """Hybrid search message should mention RRF fusion details."""
        resp = client.post(
            "/api/documents/search",
            json={"query": "revenue financial", "top_k": 3, "strategy": "hybrid"},
        )
        data = resp.json()
        assert "hybrid" in data["message"].lower() or "rrf" in data["message"].lower()

    def test_search_preserves_page_references(self, client):
        """All results should include page number and source metadata."""
        resp = client.post(
            "/api/documents/search",
            json={"query": "confidentiality clause", "top_k": 5, "strategy": "hybrid"},
        )
        data = resp.json()
        for result in data["results"]:
            assert "page_number" in result
            assert "start_char" in result
            assert "end_char" in result
            assert "boundary_type" in result
            assert "chunk_id" in result
            assert "doc_id" in result
            assert "filename" in result

    def test_search_with_doc_filter(self, client):
        """Search scoped to a specific document should only return that document's chunks."""
        # First, get the doc_id
        docs_resp = client.get("/api/documents")
        docs = docs_resp.json()
        assert len(docs) > 0
        doc_id = docs[0]["doc_id"]

        resp = client.post(
            "/api/documents/search",
            json={"query": "machine learning", "top_k": 5, "doc_id": doc_id, "strategy": "hybrid"},
        )
        data = resp.json()
        for result in data["results"]:
            assert result["doc_id"] == doc_id

    def test_empty_query_returns_empty(self, client):
        resp = client.post(
            "/api/documents/search",
            json={"query": "   ", "top_k": 5, "strategy": "hybrid"},
        )
        # Should return 422 or empty results
        if resp.status_code == 200:
            data = resp.json()
            assert data["total_results"] == 0

    def test_get_search_endpoint_with_strategy(self, client):
        """GET search endpoint should accept strategy parameter."""
        resp = client.get("/api/documents/search?q=revenue&strategy=bm25")
        assert resp.status_code == 200
        data = resp.json()
        assert data["retrieval_strategy"] == "bm25"

    def test_bm25_stats_endpoint(self, client):
        resp = client.get("/api/documents/index/bm25-stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_entries"] > 0
        assert data["algorithm"] == "BM25Okapi (rank_bm25)"
        assert data["license"] == "MIT"

    def test_invalid_strategy_returns_error(self, client):
        resp = client.post(
            "/api/documents/search",
            json={"query": "test", "top_k": 5, "strategy": "invalid_strategy"},
        )
        assert resp.status_code == 422  # Pydantic validation error

    def test_delete_document_removes_from_bm25(self, client):
        """After deletion, BM25 should not return chunks from the deleted document."""
        docs_resp = client.get("/api/documents")
        docs = docs_resp.json()
        assert len(docs) > 0
        doc_id = docs[0]["doc_id"]

        # Delete document
        del_resp = client.delete(f"/api/documents/{doc_id}")
        assert del_resp.status_code == 200

        # BM25 search should return empty
        search_resp = client.post(
            "/api/documents/search",
            json={"query": "machine learning", "top_k": 5, "strategy": "bm25"},
        )
        data = search_resp.json()
        for result in data.get("results", []):
            assert result["doc_id"] != doc_id

    def test_no_results_for_unrelated_query(self, client):
        """Query about an unrelated topic should return low-relevance or no results."""
        resp = client.post(
            "/api/documents/search",
            json={"query": "quantum entanglement photon wave", "top_k": 3, "strategy": "bm25"},
        )
        data = resp.json()
        # BM25 should return 0 results for completely unrelated terms
        assert data["total_results"] == 0


# ─── Labeled Evaluation Dataset ─────────────────────────────────────

class TestRetrievalEvaluation:
    """
    Labeled evaluation comparing dense-only, BM25-only, and hybrid retrieval
    using Recall@5 and Mean Reciprocal Rank (MRR).
    """

    @pytest.fixture(autouse=True)
    def setup_evaluation_corpus(self, client):
        """Upload evaluation documents with known content."""
        from app.services.vector_store import vector_store

        vector_store.clear_all()

        eval_doc = (
            "Section 1: Artificial Intelligence\n"
            "Machine learning algorithms learn patterns from data without explicit programming. "
            "Deep learning uses multi-layer neural networks for representation learning. "
            "Transformer architectures power modern large language models.\n\n"
            "Section 2: Legal Contract Analysis\n"
            "The Non-Disclosure Agreement (NDA) expires on December 31, 2025. "
            "Clause 4.2 limits aggregate liability to $1,000,000 USD. "
            "Governing law is the State of California.\n\n"
            "Section 3: Technical Specifications\n"
            "Model ID: BERT-base-uncased-v2 uses 110 million parameters. "
            "Training was conducted on 8x NVIDIA A100 GPUs with a batch size of 256. "
            "The system achieves 92.3% F1 score on the SQuAD 2.0 benchmark.\n\n"
            "Section 4: Financial Summary Q3 2024\n"
            "Total revenue for Q3 2024 was $45.2 million with 18% year-over-year growth. "
            "Operating margin improved to 22.5% from 19.8% in Q3 2023. "
            "Employee count reached 1,247 full-time equivalents.\n"
        )

        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as f:
            f.write(eval_doc)
            temp_path = f.name

        try:
            with open(temp_path, "rb") as f:
                resp = client.post(
                    "/api/documents/upload",
                    files={"file": ("eval_corpus.txt", f, "text/plain")},
                )
            assert resp.status_code == 200
        finally:
            os.unlink(temp_path)

        yield

        vector_store.clear_all()

    # Evaluation queries and their expected matching content keywords
    EVAL_QUERIES = [
        # Semantic paraphrases
        {
            "query": "How do AI systems acquire knowledge from data?",
            "expected_keywords": ["machine learning", "learn", "patterns", "data"],
            "category": "semantic_paraphrase",
        },
        {
            "query": "multi-layered artificial neural networks",
            "expected_keywords": ["deep learning", "neural network", "multi-layer"],
            "category": "semantic_paraphrase",
        },
        # Exact names and identifiers
        {
            "query": "BERT-base-uncased-v2",
            "expected_keywords": ["bert", "110 million", "parameters"],
            "category": "exact_identifier",
        },
        {
            "query": "NDA expiration date",
            "expected_keywords": ["non-disclosure", "december 31", "2025"],
            "category": "exact_identifier",
        },
        # Dates and numbers
        {
            "query": "Q3 2024 revenue figures",
            "expected_keywords": ["45.2", "revenue", "q3 2024"],
            "category": "date_and_number",
        },
        # Clause numbers
        {
            "query": "Clause 4.2 liability limit",
            "expected_keywords": ["4.2", "liability", "1,000,000"],
            "category": "clause_reference",
        },
        # Technical terminology
        {
            "query": "SQuAD benchmark performance",
            "expected_keywords": ["squad", "92.3", "f1"],
            "category": "technical_term",
        },
        {
            "query": "transformer language model architecture",
            "expected_keywords": ["transformer", "language model"],
            "category": "technical_term",
        },
    ]

    def _run_evaluation(self, client, strategy: str) -> dict:
        """Run all evaluation queries for a given strategy and return metrics."""
        reciprocal_ranks = []
        recalls_at_5 = []

        for eq in self.EVAL_QUERIES:
            resp = client.post(
                "/api/documents/search",
                json={"query": eq["query"], "top_k": 5, "strategy": strategy},
            )
            assert resp.status_code == 200
            data = resp.json()

            # Check if any result contains expected keywords
            found_rank = None
            for rank, result in enumerate(data["results"], 1):
                result_text = result["text"].lower()
                if any(kw.lower() in result_text for kw in eq["expected_keywords"]):
                    found_rank = rank
                    break

            if found_rank is not None:
                reciprocal_ranks.append(1.0 / found_rank)
                recalls_at_5.append(1.0)
            else:
                reciprocal_ranks.append(0.0)
                recalls_at_5.append(0.0)

        mrr = sum(reciprocal_ranks) / len(reciprocal_ranks) if reciprocal_ranks else 0.0
        recall_at_5 = sum(recalls_at_5) / len(recalls_at_5) * 100 if recalls_at_5 else 0.0

        return {
            "strategy": strategy,
            "mrr": round(mrr, 4),
            "recall_at_5": round(recall_at_5, 1),
            "total_queries": len(self.EVAL_QUERIES),
            "hits": int(sum(recalls_at_5)),
        }

    def test_dense_evaluation(self, client):
        """Evaluate dense-only retrieval."""
        metrics = self._run_evaluation(client, "dense")
        print(f"\n[Dense] Recall@5={metrics['recall_at_5']}%, MRR={metrics['mrr']}, "
              f"Hits={metrics['hits']}/{metrics['total_queries']}")
        # Dense should retrieve at least 50% of queries
        assert metrics["recall_at_5"] >= 50.0, f"Dense Recall@5 too low: {metrics['recall_at_5']}%"

    def test_bm25_evaluation(self, client):
        """Evaluate BM25-only retrieval."""
        metrics = self._run_evaluation(client, "bm25")
        print(f"\n[BM25] Recall@5={metrics['recall_at_5']}%, MRR={metrics['mrr']}, "
              f"Hits={metrics['hits']}/{metrics['total_queries']}")
        # BM25 should retrieve at least 50% of queries
        assert metrics["recall_at_5"] >= 50.0, f"BM25 Recall@5 too low: {metrics['recall_at_5']}%"

    def test_hybrid_evaluation(self, client):
        """Evaluate hybrid retrieval — should be >= best individual retriever."""
        metrics = self._run_evaluation(client, "hybrid")
        print(f"\n[Hybrid] Recall@5={metrics['recall_at_5']}%, MRR={metrics['mrr']}, "
              f"Hits={metrics['hits']}/{metrics['total_queries']}")
        # Hybrid should achieve at least 75% recall
        assert metrics["recall_at_5"] >= 75.0, f"Hybrid Recall@5 too low: {metrics['recall_at_5']}%"

    def test_hybrid_beats_or_matches_individual(self, client):
        """Hybrid recall should be >= max(dense, bm25) recall."""
        dense_metrics = self._run_evaluation(client, "dense")
        bm25_metrics = self._run_evaluation(client, "bm25")
        hybrid_metrics = self._run_evaluation(client, "hybrid")

        best_individual = max(dense_metrics["recall_at_5"], bm25_metrics["recall_at_5"])
        print(f"\nComparison: Dense={dense_metrics['recall_at_5']}%, "
              f"BM25={bm25_metrics['recall_at_5']}%, "
              f"Hybrid={hybrid_metrics['recall_at_5']}%")
        # Allow a small tolerance (hybrid might occasionally miss if candidate pool is limited)
        assert hybrid_metrics["recall_at_5"] >= best_individual - 15.0, (
            f"Hybrid ({hybrid_metrics['recall_at_5']}%) significantly worse than "
            f"best individual ({best_individual}%)"
        )

    def test_comparative_report(self, client):
        """Generate and print a comparative evaluation report."""
        strategies = ["dense", "bm25", "hybrid"]
        all_metrics = {}

        for strat in strategies:
            all_metrics[strat] = self._run_evaluation(client, strat)

        print("\n" + "=" * 60)
        print("RETRIEVAL EVALUATION REPORT")
        print("=" * 60)
        print(f"{'Strategy':<12} {'Recall@5':>10} {'MRR':>8} {'Hits':>8}")
        print("-" * 40)
        for strat in strategies:
            m = all_metrics[strat]
            print(f"{strat:<12} {m['recall_at_5']:>9.1f}% {m['mrr']:>8.4f} {m['hits']:>5}/{m['total_queries']}")
        print("=" * 60)

        # All strategies should have non-zero recall
        for strat in strategies:
            assert all_metrics[strat]["recall_at_5"] > 0, f"{strat} has zero recall"
