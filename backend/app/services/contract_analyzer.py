"""
Contract Intelligence Analysis Service
======================================
Integrates the existing CUAD Category Trigger Baseline Extractor for optional
academic legal contract analysis on indexed documents.

Invariants:
1. Isolated from general-purpose Q&A and hybrid retrieval.
2. Lightweight lexical trigger evaluation on CPU; no transformers or model downloads.
3. Strict provenance and source attribution to original pages and character offsets.
4. Distinguishes 'not detected' by heuristic from verified legal absence.
5. Mandatory academic disclaimer attached to every response.
"""

import time
import logging
from typing import List, Optional, Dict, Any

from app.schemas.contract import (
    ContractAnalysisRequest,
    ContractAnalysisResponse,
    ClauseSpan,
)
from app.services.vector_store import VectorStore
from app.experiments.cuad.baseline_extractor import (
    CUADBaselineExtractor,
    CATEGORY_TRIGGERS,
)

logger = logging.getLogger(__name__)


class ContractAnalyzerService:
    """
    Analyzes uploaded and indexed contract documents using the 41 CUAD trigger categories.
    """

    def __init__(self, vector_store: VectorStore):
        self.vector_store = vector_store

    def get_supported_categories(self) -> List[str]:
        """Return the list of 41 CUAD category names supported by the extractor."""
        return list(CATEGORY_TRIGGERS.keys())

    def analyze_document(
        self,
        doc_id: str,
        confidence_threshold: float = 3.0,
        categories: Optional[List[str]] = None,
    ) -> ContractAnalysisResponse:
        """
        Analyze a specific indexed document for CUAD clause categories.

        Args:
            doc_id: Document ID to analyze.
            confidence_threshold: Minimum trigger match score (tuned baseline default: 3.0).
            categories: Optional list of specific categories to run (defaults to all 41).

        Returns:
            ContractAnalysisResponse with provenance, extracted spans, and academic disclaimer.

        Raises:
            ValueError: If the document is not found in the vector store.
        """
        start_time = time.time()

        # 1. Retrieve document metadata
        doc = self.vector_store.get_document(doc_id)
        if not doc:
            raise ValueError(f"Document with ID '{doc_id}' not found.")

        # 2. Retrieve document chunk records
        chunks = self.vector_store.get_document_chunks(doc_id)

        # 3. Determine target categories
        available_categories = self.get_supported_categories()
        if categories:
            # Preserve order of requested categories, filtering to valid CUAD categories
            target_categories = [c for c in categories if c in CATEGORY_TRIGGERS]
            if not target_categories:
                target_categories = available_categories
        else:
            target_categories = available_categories

        extractor = CUADBaselineExtractor(confidence_threshold=confidence_threshold)
        results: List[ClauseSpan] = []

        # 4. If document contains no text chunks (e.g. empty or unextractable)
        if not chunks:
            for cat in target_categories:
                results.append(
                    ClauseSpan(
                        category=cat,
                        detected=False,
                        extracted_text=None,
                        doc_id=doc_id,
                        filename=doc.filename,
                        page_number=None,
                        start_char=None,
                        end_char=None,
                        is_approximate=False,
                        boundary_type=None,
                        confidence_score=0.0,
                        detection_status="not_detected",
                        explanation="Document contains no indexed text chunks for analysis.",
                    )
                )
            elapsed_ms = round((time.time() - start_time) * 1000.0, 2)
            return ContractAnalysisResponse(
                doc_id=doc_id,
                filename=doc.filename,
                total_pages=doc.total_pages,
                total_chunks_scanned=0,
                categories_analyzed=len(target_categories),
                clauses_detected_count=0,
                clauses_not_detected_count=len(target_categories),
                results=results,
                latency_ms=elapsed_ms,
            )

        # 5. Execute trigger baseline extraction per category
        for cat in target_categories:
            best_candidate = ""
            best_score = 0.0
            best_chunk = None
            best_s_start = -1
            best_s_end = -1

            for chunk in chunks:
                if not chunk.text or not chunk.text.strip():
                    continue

                candidate, s_start, s_end, score = extractor.extract_clause(
                    context=chunk.text,
                    category=cat,
                    question="",
                )

                if score > best_score:
                    best_score = score
                    best_candidate = candidate
                    best_chunk = chunk
                    best_s_start = s_start
                    best_s_end = s_end

            # Check if best candidate meets threshold
            if best_candidate and best_score >= confidence_threshold and best_chunk is not None:
                # Map chunk-level character offset to page-level character offset
                page_start = best_chunk.start_char + best_s_start
                page_end = best_chunk.start_char + best_s_end

                results.append(
                    ClauseSpan(
                        category=cat,
                        detected=True,
                        extracted_text=best_candidate,
                        doc_id=doc_id,
                        filename=doc.filename,
                        page_number=best_chunk.page_number,
                        start_char=page_start,
                        end_char=page_end,
                        is_approximate=best_chunk.is_approximate,
                        boundary_type=best_chunk.boundary_type,
                        confidence_score=round(best_score, 2),
                        detection_status="detected",
                        explanation=(
                            f"Candidate clause detected with heuristic trigger score {best_score:.1f} "
                            f"on page {best_chunk.page_number}."
                        ),
                    )
                )
            else:
                # Distinct from absence: report as not detected by the heuristic
                results.append(
                    ClauseSpan(
                        category=cat,
                        detected=False,
                        extracted_text=None,
                        doc_id=doc_id,
                        filename=doc.filename,
                        page_number=None,
                        start_char=None,
                        end_char=None,
                        is_approximate=False,
                        boundary_type=None,
                        confidence_score=0.0,
                        detection_status="not_detected",
                        explanation="Not detected by the experimental extractor. This does not verify legal absence.",
                    )
                )

        detected_count = sum(1 for r in results if r.detected)
        not_detected_count = len(results) - detected_count
        elapsed_ms = round((time.time() - start_time) * 1000.0, 2)

        return ContractAnalysisResponse(
            doc_id=doc_id,
            filename=doc.filename,
            total_pages=doc.total_pages,
            total_chunks_scanned=len(chunks),
            categories_analyzed=len(target_categories),
            clauses_detected_count=detected_count,
            clauses_not_detected_count=not_detected_count,
            results=results,
            latency_ms=elapsed_ms,
        )
