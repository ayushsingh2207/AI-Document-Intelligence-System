from typing import Optional, Literal
from fastapi import APIRouter, HTTPException, Query, Request, status
from app.config import settings
from app.services.limiter import limiter
from app.services.vector_store import vector_store
from app.services.bm25_store import bm25_store
from app.services.hybrid_retriever import HybridRetriever, RetrievalStrategy
from app.schemas.chunk import SearchQuery, SearchResponse, IndexStatsResponse, BM25StatsResponse

router = APIRouter(prefix="/api/documents", tags=["Hybrid Search & Index"])

# Module-level hybrid retriever singleton (uses vector_store's active bm25 instance)
_hybrid_retriever = HybridRetriever(vector_store=vector_store, bm25_store=vector_store.bm25)

@router.post("/search", response_model=SearchResponse)
@limiter.limit(settings.RATE_LIMIT_SEARCH)
async def hybrid_search_post(request: Request, query_payload: SearchQuery):
    """
    Execute a retrieval query using the specified strategy.

    Strategies:
    - **dense**: FAISS cosine similarity only (Phase 2 behavior)
    - **bm25**: BM25 lexical keyword matching only
    - **hybrid** (default): Reciprocal Rank Fusion of dense + BM25

    Returns ranked chunks with relevance scores and source page references.
    """
    try:
        strategy = RetrievalStrategy(query_payload.strategy)
        response = _hybrid_retriever.search(
            query=query_payload.query,
            top_k=query_payload.top_k,
            doc_id=query_payload.doc_id,
            min_score=query_payload.min_score,
            strategy=strategy,
        )
        return response
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid retrieval strategy: {str(exc)}"
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(exc)}"
        )

@router.get("/search", response_model=SearchResponse)
@limiter.limit(settings.RATE_LIMIT_SEARCH)
async def hybrid_search_get(
    request: Request,
    q: str = Query(..., min_length=1, description="Search query string"),
    top_k: int = Query(default=5, ge=1, le=50, description="Max results"),
    doc_id: Optional[str] = Query(default=None, description="Optional document ID filter"),
    min_score: float = Query(default=0.0, ge=0.0, le=1.0, description="Minimum score threshold"),
    strategy: Literal["dense", "bm25", "hybrid"] = Query(
        default="hybrid", description="Retrieval strategy"
    )
):
    """GET variant of hybrid search."""
    return await hybrid_search_post(
        request,
        SearchQuery(query=q, top_k=top_k, doc_id=doc_id, min_score=min_score, strategy=strategy)
    )

@router.get("/index/stats", response_model=IndexStatsResponse)
async def get_index_stats():
    """Returns vector index size, embedding model metadata, dimension, and memory stats."""
    return vector_store.get_stats()

@router.get("/index/bm25-stats", response_model=BM25StatsResponse)
async def get_bm25_stats():
    """Returns BM25 lexical index statistics."""
    stats = bm25_store.get_stats()
    return BM25StatsResponse(**stats)
