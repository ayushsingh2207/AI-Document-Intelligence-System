import os
import shutil
import tempfile
import pytest
from fastapi.testclient import TestClient
from app.config import settings
from app.main import app
from app.services.vector_store import VectorStore
from app.services.bm25_store import BM25Store
from app.services.demo_corpus import (
    ensure_demo_corpus_indexed,
    DEMO_DOC_TRANSFORMER_ID,
    DEMO_DOC_CONTRACT_ID,
    APPROVED_DEMO_DOC_IDS,
)
from app.schemas.document import DocumentPage

client = TestClient(app)


class TestDemoModeRestrictions:
    """Verifies that in DEMO_MODE, mutation operations (upload & delete) are strictly rejected."""

    def setup_method(self):
        from app.services.limiter import limiter
        limiter.reset()
        self._orig_demo = settings.DEMO_MODE
        settings.DEMO_MODE = True

    def teardown_method(self):
        settings.DEMO_MODE = self._orig_demo

    def test_upload_rejected_in_demo_mode(self):
        """Anonymous upload requests must be rejected with 403 Forbidden in demo mode."""
        dummy_file = ("test.txt", b"Hello world content", "text/plain")
        response = client.post("/api/documents/upload", files={"file": dummy_file})
        assert response.status_code == 403
        data = response.json()
        assert "disabled in public demo mode" in data["detail"].lower()

    def test_delete_rejected_in_demo_mode(self):
        """Document deletion must be rejected with 403 Forbidden in demo mode."""
        response = client.delete(f"/api/documents/{DEMO_DOC_CONTRACT_ID}")
        assert response.status_code == 403
        data = response.json()
        assert "disabled in public demo mode" in data["detail"].lower()


class TestDemoCorpusIsolation:
    """Verifies that demo mode strictly isolates the demo corpus and never exposes private documents."""

    def setup_method(self):
        self._orig_demo = settings.DEMO_MODE
        self._orig_data_dir = settings.DATA_DIR
        self._orig_demo_data_dir = settings.DEMO_DATA_DIR

        # Create isolated temp directories for private and demo storage
        self.temp_private_dir = tempfile.mkdtemp(prefix="test_private_")
        self.temp_demo_dir = tempfile.mkdtemp(prefix="test_demo_")

        settings.DATA_DIR = self.temp_private_dir
        settings.DEMO_DATA_DIR = self.temp_demo_dir
        settings.DEMO_MODE = True

        # 1. Create a simulated private document in the private store
        private_bm25 = BM25Store(data_dir=self.temp_private_dir)
        self.private_store = VectorStore(
            dimension=384,
            data_dir=self.temp_private_dir,
            bm25_store_instance=private_bm25
        )
        self.private_doc_id = "doc_secret_internal_report"
        self.private_store.index_document(
            doc_id=self.private_doc_id,
            filename="confidential_q4_metrics.txt",
            file_type="txt",
            file_size_bytes=500,
            pages=[
                DocumentPage(
                    page_number=1,
                    text="CONFIDENTIAL INTERNAL ONLY: Q4 proprietary product margins reached 84 percent.",
                    char_count=82,
                    word_count=10,
                )
            ],
            metadata={"confidential": True},
            is_sample=False,
            chunk_size=500,
            chunk_overlap=50,
        )

        # 2. Initialize isolated demo store with approved demo corpus
        demo_bm25 = BM25Store(data_dir=self.temp_demo_dir)
        self.demo_store = VectorStore(
            dimension=384,
            data_dir=self.temp_demo_dir,
            bm25_store_instance=demo_bm25
        )
        ensure_demo_corpus_indexed(self.demo_store)

    def teardown_method(self):
        settings.DEMO_MODE = self._orig_demo
        settings.DATA_DIR = self._orig_data_dir
        settings.DEMO_DATA_DIR = self._orig_demo_data_dir
        shutil.rmtree(self.temp_private_dir, ignore_errors=True)
        shutil.rmtree(self.temp_demo_dir, ignore_errors=True)

    def test_demo_corpus_contains_only_approved_documents(self):
        """Demo store must contain only the approved demo document IDs."""
        indexed_docs = self.demo_store.list_documents()
        doc_ids = {d.doc_id for d in indexed_docs}
        assert doc_ids == APPROVED_DEMO_DOC_IDS
        assert self.private_doc_id not in doc_ids

    def test_private_document_inaccessible_in_demo_store(self):
        """Direct access to private document IDs must return None in demo store."""
        assert self.demo_store.get_document(self.private_doc_id) is None
        assert self.demo_store.get_document_chunks(self.private_doc_id) == []

    def test_search_cannot_retrieve_private_document(self):
        """Passage search in the demo store must never match or leak private documents."""
        from app.services.hybrid_retriever import HybridRetriever, RetrievalStrategy
        demo_retriever = HybridRetriever(vector_store=self.demo_store, bm25_store=self.demo_store.bm25)

        res = demo_retriever.search(
            query="proprietary product margins",
            top_k=5,
            strategy=RetrievalStrategy.HYBRID
        )
        for r in res.results:
            assert r.doc_id != self.private_doc_id
            assert "CONFIDENTIAL" not in r.text

    def test_qa_abstains_and_does_not_leak_private_document(self):
        """Grounded Q&A in demo store must abstain and never cite private documents."""
        from app.services.hybrid_retriever import HybridRetriever
        from app.services.embedding_service import embedding_service
        from app.services.grounded_qa import GroundedQAService
        from app.schemas.qa import QARequest

        demo_retriever = HybridRetriever(vector_store=self.demo_store, bm25_store=self.demo_store.bm25)
        qa_service = GroundedQAService(
            hybrid_retriever=demo_retriever,
            vector_store=self.demo_store,
            embedder=embedding_service,
        )

        qa_res = qa_service.answer_question(
            QARequest(question="What are the proprietary product margins in Q4?")
        )
        assert qa_res.answered is False
        assert qa_res.abstention_reason == "insufficient_evidence"
        for c in qa_res.citations:
            assert c.doc_id != self.private_doc_id

    def test_contract_analysis_on_demo_contract(self):
        """CUAD Contract intelligence functions properly on the approved demo contract."""
        from app.services.contract_analyzer import ContractAnalyzerService
        analyzer = ContractAnalyzerService(vector_store=self.demo_store)

        analysis = analyzer.analyze_document(DEMO_DOC_CONTRACT_ID)
        assert analysis.categories_analyzed == 41
        gov_law = next((d for d in analysis.results if d.category == "Governing Law"), None)
        assert gov_law is not None
        assert gov_law.detected is True
        assert "Delaware" in gov_law.extracted_text


class TestRateLimiting:
    """Verifies rate limiting responses."""

    def test_rate_limit_exceeded_returns_429(self):
        """Bursting requests beyond rate limit must return HTTP 429 with Retry-After header."""
        from slowapi import Limiter
        from slowapi.util import get_remote_address
        from slowapi.errors import RateLimitExceeded
        from fastapi import FastAPI, Request
        from fastapi.responses import JSONResponse

        test_app = FastAPI()
        test_limiter = Limiter(key_func=get_remote_address)
        test_app.state.limiter = test_limiter

        @test_app.exception_handler(RateLimitExceeded)
        async def rl_handler(request: Request, exc: RateLimitExceeded):
            return JSONResponse(
                status_code=429,
                content={"error": "Rate limit exceeded", "detail": str(exc)},
                headers={"Retry-After": "60"}
            )

        @test_app.get("/rate-limited")
        @test_limiter.limit("2/minute")
        def limited_route(request: Request):
            return {"status": "ok"}

        tc = TestClient(test_app)
        r1 = tc.get("/rate-limited")
        r2 = tc.get("/rate-limited")
        r3 = tc.get("/rate-limited")

        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r3.status_code == 429
        assert "Retry-After" in r3.headers


class TestProductionConfigurationValidation:
    """Verifies that production configuration never silently falls back to localhost."""

    def setup_method(self):
        self._orig_env = settings.ENVIRONMENT
        self._orig_origins = os.environ.get("ALLOWED_ORIGINS")

    def teardown_method(self):
        settings.ENVIRONMENT = self._orig_env
        if self._orig_origins is not None:
            os.environ["ALLOWED_ORIGINS"] = self._orig_origins
        elif "ALLOWED_ORIGINS" in os.environ:
            del os.environ["ALLOWED_ORIGINS"]

    def test_production_without_origins_raises_error(self):
        """Running in production without configured ALLOWED_ORIGINS must raise ValueError."""
        settings.ENVIRONMENT = "production"
        if "ALLOWED_ORIGINS" in os.environ:
            del os.environ["ALLOWED_ORIGINS"]

        with pytest.raises(ValueError) as excinfo:
            settings.validate_production_configuration()
        assert "ALLOWED_ORIGINS must be set" in str(excinfo.value)

    def test_production_with_valid_origins_passes(self):
        """Running in production with valid public origin passes validation."""
        settings.ENVIRONMENT = "production"
        os.environ["ALLOWED_ORIGINS"] = "https://ai-document-intelligence.vercel.app"

        # Should not raise
        settings.validate_production_configuration()
        assert "https://ai-document-intelligence.vercel.app" in settings.cors_origins
