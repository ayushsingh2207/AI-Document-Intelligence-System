from typing import List, Optional
from pydantic import BaseModel, Field


class ContractAnalysisRequest(BaseModel):
    confidence_threshold: float = Field(
        default=3.0,
        ge=0.5,
        le=10.0,
        description="Confidence threshold for CUAD trigger baseline (Phase 4 tuned default: 3.0)"
    )
    categories: Optional[List[str]] = Field(
        default=None,
        description="Optional subset of the 41 CUAD categories to analyze. Defaults to all 41 categories."
    )


class ClauseSpan(BaseModel):
    category: str = Field(..., description="CUAD clause category name (1 of 41)")
    detected: bool = Field(..., description="True if candidate clause was detected by trigger baseline")
    extracted_text: Optional[str] = Field(default=None, description="Exact extracted candidate span from document")
    doc_id: str = Field(..., description="Document identifier")
    filename: str = Field(..., description="Source document filename")
    page_number: Optional[int] = Field(default=None, description="1-indexed source page number")
    start_char: Optional[int] = Field(default=None, description="Character offset start in the source page text")
    end_char: Optional[int] = Field(default=None, description="Character offset end in the source page text")
    is_approximate: bool = Field(default=False, description="True if page boundary was approximated (e.g. unpaginated TXT)")
    boundary_type: Optional[str] = Field(default=None, description="Demarcation boundary type")
    confidence_score: float = Field(default=0.0, description="Heuristic trigger/overlap score")
    detection_status: str = Field(
        ...,
        description="'detected' if clause found, 'not_detected' if below threshold (strictly distinguishes no detection from verified absence)"
    )
    explanation: str = Field(
        ...,
        description="Human-readable explanation of the extraction result"
    )


class ContractAnalysisResponse(BaseModel):
    doc_id: str = Field(..., description="Analyzed document identifier")
    filename: str = Field(..., description="Analyzed document filename")
    total_pages: int = Field(..., description="Total pages in the analyzed document")
    total_chunks_scanned: int = Field(..., description="Number of semantic chunks scanned")
    categories_analyzed: int = Field(..., description="Total categories evaluated (up to 41)")
    clauses_detected_count: int = Field(..., description="Number of categories where a candidate clause was detected")
    clauses_not_detected_count: int = Field(..., description="Number of categories with no detection by the baseline")
    disclaimer: str = Field(
        default=(
            "ACADEMIC DEMONSTRATION ONLY: This analysis is produced by an experimental heuristic "
            "trigger extractor (CUAD baseline). It does NOT constitute legal advice, formal contract review, "
            "or guarantee of completeness. A status of 'not detected' indicates the heuristic pattern was not "
            "found above the confidence threshold, NOT that the clause is absent from the contract."
        ),
        description="Mandatory legal disclaimer clarifying experimental academic nature"
    )
    results: List[ClauseSpan] = Field(default_factory=list, description="Category-by-category clause extraction results")
    latency_ms: float = Field(default=0.0, description="Analysis latency in milliseconds")
