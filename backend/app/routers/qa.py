import logging
from fastapi import APIRouter, HTTPException, Request, status
from app.config import settings
from app.services.limiter import limiter
from app.services.vector_store import vector_store
from app.services.bm25_store import bm25_store
from app.services.embedding_service import embedding_service
from app.services.hybrid_retriever import HybridRetriever
from app.services.grounded_qa import GroundedQAService
from app.schemas.qa import QARequest, QAResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["Grounded Q&A"])

# Reuse existing module-level retrieval and storage singletons (uses active vector_store.bm25)
_hybrid_retriever = HybridRetriever(vector_store=vector_store, bm25_store=vector_store.bm25)
_qa_service = GroundedQAService(
    hybrid_retriever=_hybrid_retriever,
    vector_store=vector_store,
    embedder=embedding_service,
)


@router.post("/qa", response_model=QAResponse)
@limiter.limit(settings.RATE_LIMIT_QA)
async def answer_document_question(request: Request, qa_payload: QARequest):
    """
    Answer questions using evidence retrieved from indexed documents with verifiable citations.

    - **Evidence Grounding**: Retrieves relevant passages using Hybrid Retrieval (Dense + BM25 + RRF)
      and evaluates sentence-level semantic and lexical support.
    - **Verifiable Citations**: Every positive answer includes document ID, filename, page number,
      exact character offsets, and supporting excerpt.
    - **Conservative Abstention**: If evidence is absent, conflicting, or falls below confidence threshold,
      returns an explicit abstention response without fabricated citations.
    - **Scope Enforcement**: If `doc_id` is supplied, evidence is strictly confined to that document.
    """
    try:
        # Check empty or whitespace query
        if not qa_payload.question or not qa_payload.question.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Question cannot be empty or contain only whitespace.",
            )

        response = _qa_service.answer_question(qa_payload)
        return response
    except ValueError as exc:
        msg = str(exc)
        if "not found" in msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=msg,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Unhandled exception during grounded Q&A: %s", str(exc), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Grounded Q&A processing failed: {str(exc)}",
        )
