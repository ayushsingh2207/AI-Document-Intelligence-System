"""
Hybrid Retrieval Engine
========================
Combines FAISS dense vector retrieval (semantic similarity via all-MiniLM-L6-v2)
with BM25 lexical retrieval (keyword matching via rank_bm25) using
Reciprocal Rank Fusion (RRF).

RRF Formula:
    RRF_score(d) = Σ  1 / (k + rank_i(d))
                   i

Where k is a constant (default 60) and rank_i(d) is the 1-based rank of
document d in retrieval list i. Higher RRF scores indicate stronger combined
relevance.

Supported retrieval strategies:
- "dense"  : Dense-only (FAISS cosine similarity) — Phase 2 behavior
- "bm25"   : BM25-only (lexical keyword matching) — new Phase 3 capability
- "hybrid" : Reciprocal Rank Fusion of dense + BM25 — new Phase 3 default

Deduplication:
    When the same chunk appears in both dense and BM25 result lists,
    its RRF score is the sum of both reciprocal ranks. Each unique
    chunk_id appears exactly once in the fused output.
"""

import time
import logging
from typing import List, Dict, Optional, Literal, Tuple
from enum import Enum

from app.schemas.chunk import SearchResult, SearchResponse
from app.services.embedding_service import embedding_service
from app.services.vector_store import VectorStore
from app.services.bm25_store import BM25Store

logger = logging.getLogger(__name__)


class RetrievalStrategy(str, Enum):
    DENSE = "dense"
    BM25 = "bm25"
    HYBRID = "hybrid"


# RRF constant k — standard default from the original RRF paper (Cormack et al. 2009)
DEFAULT_RRF_K = 60


def reciprocal_rank_fusion(
    ranked_lists: List[List[Tuple[str, float]]],
    k: int = DEFAULT_RRF_K,
) -> List[Tuple[str, float]]:
    """
    Fuse multiple ranked result lists using Reciprocal Rank Fusion.

    Args:
        ranked_lists: List of ranked lists, each containing (chunk_id, original_score) tuples.
                      Items are assumed to be in descending order of relevance.
        k: RRF constant (default 60).

    Returns:
        Fused list of (chunk_id, rrf_score) sorted by descending RRF score.
        Each chunk_id appears exactly once (deduplication built-in).
    """
    fused_scores: Dict[str, float] = {}

    for ranked_list in ranked_lists:
        for rank_position, (chunk_id, _original_score) in enumerate(ranked_list):
            # rank_position is 0-indexed; RRF uses 1-indexed ranks
            rrf_contribution = 1.0 / (k + rank_position + 1)
            fused_scores[chunk_id] = fused_scores.get(chunk_id, 0.0) + rrf_contribution

    # Sort by fused score descending
    fused = sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)
    return fused


class HybridRetriever:
    """
    Orchestrates retrieval across dense (FAISS) and lexical (BM25) indexes,
    fusing results with Reciprocal Rank Fusion when the hybrid strategy is selected.
    """

    def __init__(self, vector_store: VectorStore, bm25_store: BM25Store):
        self.vector_store = vector_store
        self.bm25_store = bm25_store

    def search(
        self,
        query: str,
        top_k: int = 5,
        doc_id: Optional[str] = None,
        min_score: float = 0.0,
        strategy: RetrievalStrategy = RetrievalStrategy.HYBRID,
        rrf_k: int = DEFAULT_RRF_K,
    ) -> SearchResponse:
        """
        Execute a retrieval query using the specified strategy.

        Args:
            query: Natural language search query.
            top_k: Maximum number of results to return.
            doc_id: Optional document ID filter.
            min_score: Minimum score threshold (only applies to dense-only mode).
            strategy: Retrieval strategy — "dense", "bm25", or "hybrid".
            rrf_k: RRF constant k (only used in hybrid mode).

        Returns:
            SearchResponse with ranked results and metadata.
        """
        start_time = time.time()
        clean_query = query.strip()

        if not clean_query:
            return SearchResponse(
                query=query,
                total_results=0,
                results=[],
                search_time_ms=0.0,
                latency_ms=0.0,
                model=embedding_service.MODEL_NAME,
                model_name=embedding_service.MODEL_NAME,
                retrieval_strategy=strategy.value,
                message="Query was empty",
            )

        if len(self.vector_store._vector_to_chunk) == 0 and len(self.bm25_store._corpus) == 0:
            return SearchResponse(
                query=query,
                total_results=0,
                results=[],
                search_time_ms=0.0,
                latency_ms=0.0,
                model=embedding_service.MODEL_NAME,
                model_name=embedding_service.MODEL_NAME,
                retrieval_strategy=strategy.value,
                message="Index is empty. Please upload documents first.",
            )

        if strategy == RetrievalStrategy.DENSE:
            return self._dense_search(
                clean_query, top_k, doc_id, min_score, start_time
            )
        elif strategy == RetrievalStrategy.BM25:
            return self._bm25_search(clean_query, top_k, doc_id, start_time)
        else:  # HYBRID
            return self._hybrid_search(
                clean_query, top_k, doc_id, min_score, rrf_k, start_time
            )

    def _dense_search(
        self,
        query: str,
        top_k: int,
        doc_id: Optional[str],
        min_score: float,
        start_time: float,
    ) -> SearchResponse:
        """Dense-only retrieval via existing vector store (Phase 2 backward compatibility)."""
        response = self.vector_store.search(
            query=query, top_k=top_k, doc_id=doc_id, min_score=min_score
        )
        response.retrieval_strategy = "dense"
        return response

    def _bm25_search(
        self,
        query: str,
        top_k: int,
        doc_id: Optional[str],
        start_time: float,
    ) -> SearchResponse:
        """BM25-only lexical retrieval."""
        # Fetch more candidates than needed for filtering
        bm25_results = self.bm25_store.search(
            query=query, top_k=top_k * 2, doc_id=doc_id
        )

        results = self._build_results_from_chunk_ids(
            [(cid, score) for cid, score in bm25_results],
            top_k=top_k,
            normalize_scores=True,
        )

        elapsed_ms = round((time.time() - start_time) * 1000.0, 2)
        return SearchResponse(
            query=query,
            total_results=len(results),
            results=results,
            search_time_ms=elapsed_ms,
            latency_ms=elapsed_ms,
            model="BM25Okapi (rank_bm25)",
            model_name="BM25Okapi (rank_bm25)",
            retrieval_strategy="bm25",
            message=f"Found {len(results)} matching chunk(s) via BM25 lexical search",
        )

    def _hybrid_search(
        self,
        query: str,
        top_k: int,
        doc_id: Optional[str],
        min_score: float,
        rrf_k: int,
        start_time: float,
    ) -> SearchResponse:
        """
        Hybrid retrieval: fetch candidates from both dense and BM25,
        then fuse with Reciprocal Rank Fusion.
        """
        # Fetch a larger candidate pool from each retriever for better fusion coverage
        candidate_k = max(top_k * 3, 20)

        # Dense retrieval
        dense_response = self.vector_store.search(
            query=query, top_k=candidate_k, doc_id=doc_id, min_score=0.0
        )
        dense_ranked = [
            (r.chunk_id, r.score) for r in dense_response.results
        ]

        # BM25 retrieval
        bm25_ranked = self.bm25_store.search(
            query=query, top_k=candidate_k, doc_id=doc_id
        )

        # Reciprocal Rank Fusion
        fused = reciprocal_rank_fusion(
            [dense_ranked, bm25_ranked], k=rrf_k
        )

        # Build result objects from fused chunk IDs
        results = self._build_results_from_chunk_ids(
            fused, top_k=top_k, normalize_scores=True
        )

        elapsed_ms = round((time.time() - start_time) * 1000.0, 2)

        dense_count = len(dense_ranked)
        bm25_count = len(bm25_ranked)
        both_count = len(set(cid for cid, _ in dense_ranked) & set(cid for cid, _ in bm25_ranked))

        return SearchResponse(
            query=query,
            total_results=len(results),
            results=results,
            search_time_ms=elapsed_ms,
            latency_ms=elapsed_ms,
            model=embedding_service.MODEL_NAME,
            model_name=embedding_service.MODEL_NAME,
            retrieval_strategy="hybrid",
            message=(
                f"Found {len(results)} chunk(s) via hybrid retrieval "
                f"(Dense: {dense_count}, BM25: {bm25_count}, "
                f"Overlap: {both_count}, Fusion: RRF k={rrf_k})"
            ),
        )

    def _build_results_from_chunk_ids(
        self,
        scored_chunks: List[Tuple[str, float]],
        top_k: int,
        normalize_scores: bool = True,
    ) -> List[SearchResult]:
        """
        Look up chunk metadata from the vector store and build SearchResult objects.
        Scores are optionally normalized to [0, 1] for display consistency.
        """
        if not scored_chunks:
            return []

        # Normalize scores to [0, 1]
        if normalize_scores and scored_chunks:
            max_score = max(s for _, s in scored_chunks) if scored_chunks else 1.0
            if max_score > 0:
                scored_chunks = [(cid, s / max_score) for cid, s in scored_chunks]

        results: List[SearchResult] = []
        chunk_map = self.vector_store._vector_to_chunk

        for chunk_id, score in scored_chunks[:top_k]:
            # Find the chunk in the vector store metadata
            chunk = None
            for _vid, c in chunk_map.items():
                if c.chunk_id == chunk_id:
                    chunk = c
                    break

            if chunk is None:
                continue

            results.append(
                SearchResult(
                    chunk_id=chunk.chunk_id,
                    doc_id=chunk.doc_id,
                    filename=chunk.filename,
                    page_number=chunk.page_number,
                    chunk_index=chunk.chunk_index,
                    score=round(score, 4),
                    text=chunk.text,
                    start_char=chunk.start_char,
                    end_char=chunk.end_char,
                    boundary_type=chunk.boundary_type,
                    is_approximate=chunk.is_approximate,
                    word_count=chunk.word_count,
                    char_count=chunk.char_count,
                )
            )

        return results
