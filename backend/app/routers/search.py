from typing import Optional
from fastapi import APIRouter, HTTPException, Query, status
from app.services.vector_store import vector_store
from app.schemas.chunk import SearchQuery, SearchResponse, IndexStatsResponse

router = APIRouter(prefix="/api/documents", tags=["Semantic Search & Index"])

@router.post("/search", response_model=SearchResponse)
async def semantic_search_post(query_payload: SearchQuery):
    """
    Execute semantic similarity search using dense vector representations (all-MiniLM-L6-v2)
    and FAISS IndexFlatIP.
    Returns ranked chunks with similarity scores (0.0 to 1.0) and source page references.
    """
    try:
        response = vector_store.search(
            query=query_payload.query,
            top_k=query_payload.top_k,
            doc_id=query_payload.doc_id,
            min_score=query_payload.min_score
        )
        return response
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Semantic search failed: {str(exc)}"
        )

@router.get("/search", response_model=SearchResponse)
async def semantic_search_get(
    q: str = Query(..., min_length=1, description="Search query string"),
    top_k: int = Query(default=5, ge=1, le=50, description="Max results"),
    doc_id: Optional[str] = Query(default=None, description="Optional document ID filter"),
    min_score: float = Query(default=0.0, ge=0.0, le=1.0, description="Minimum cosine similarity threshold")
):
    """GET variant of semantic similarity search."""
    return await semantic_search_post(
        SearchQuery(query=q, top_k=top_k, doc_id=doc_id, min_score=min_score)
    )

@router.get("/index/stats", response_model=IndexStatsResponse)
async def get_index_stats():
    """Returns vector index size, embedding model metadata, dimension, and memory stats."""
    return vector_store.get_stats()
