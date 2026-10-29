from typing import List, Optional
from pydantic import BaseModel, Field


class Citation(BaseModel):
    citation_id: str = Field(..., description="Unique citation identifier e.g. cit_1")
    doc_id: str = Field(..., description="Parent document identifier")
    filename: str = Field(..., description="Source document filename")
    page_number: int = Field(..., description="1-indexed source page number")
    chunk_id: str = Field(..., description="Source chunk identifier")
    start_char: int = Field(..., description="Character offset start in the source page text")
    end_char: int = Field(..., description="Character offset end in the source page text")
    supporting_excerpt: str = Field(..., description="Exact supporting text excerpt from the document")
    boundary_type: str = Field(default="physical", description="Demarcation boundary type")
    is_approximate: bool = Field(default=False, description="True if page boundary was approximated")
    relevance_score: float = Field(..., description="Evidence relevance confidence score (0.0 to 1.0)")


class QARequest(BaseModel):
    question: str = Field(..., min_length=1, description="Natural language question to answer from uploaded documents")
    doc_id: Optional[str] = Field(default=None, description="Optional document ID to scope the question to")
    top_k: int = Field(default=5, ge=1, le=20, description="Maximum number of candidate chunks to retrieve for evidence")
    confidence_threshold: float = Field(default=0.45, ge=0.0, le=1.0, description="Conservative confidence threshold for answering")


class QAResponse(BaseModel):
    question: str = Field(..., description="The query string answered or evaluated")
    answered: bool = Field(..., description="True if sufficient evidence was found, False if abstaining")
    answer: str = Field(..., description="Concise extractive answer supported by evidence, or explicit abstention message")
    confidence: float = Field(..., description="Calibrated evidence confidence score (0.0 to 1.0)")
    abstention_reason: Optional[str] = Field(
        default=None,
        description="Reason for abstention if answered is False (e.g. 'insufficient_evidence', 'empty_query', 'index_empty')"
    )
    citations: List[Citation] = Field(default_factory=list, description="Grounding source citations supporting the answer")
    retrieval_strategy: str = Field(default="hybrid", description="Retrieval strategy used to gather evidence")
    latency_ms: float = Field(default=0.0, description="End-to-end question answering latency in milliseconds")
