from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class ChunkRecord(BaseModel):
    chunk_id: str = Field(..., description="Unique deterministic chunk identifier e.g. doc_p1_c0")
    doc_id: str = Field(..., description="Parent document identifier")
    filename: str = Field(..., description="Original filename")
    page_number: int = Field(..., description="1-indexed source page number")
    chunk_index: int = Field(..., description="Sequential index of chunk within page or document")
    start_char: int = Field(..., description="Start character offset in page text")
    end_char: int = Field(..., description="End character offset in page text")
    boundary_type: str = Field(..., description="Demarcation type: physical, explicit_break, form_feed, approximate_section, approximate_chunk")
    is_approximate: bool = Field(..., description="True if page boundary was approximated")
    text: str = Field(..., description="Raw text content of the chunk")
    char_count: int = Field(..., description="Number of characters in the chunk")
    word_count: int = Field(..., description="Number of words in the chunk")

class DocumentSummary(BaseModel):
    doc_id: str
    filename: str
    file_type: str
    file_size_bytes: int
    file_size_formatted: str
    total_pages: int
    total_words: int
    total_chunks: int
    preview_text: str
    is_sample: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str

class SearchQuery(BaseModel):
    query: str = Field(..., min_length=1, description="Natural language search query")
    top_k: int = Field(default=5, ge=1, le=50, description="Maximum number of ranked results to return")
    doc_id: Optional[str] = Field(default=None, description="Optional document ID to scope the search")
    min_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Minimum cosine similarity threshold (0.0 to 1.0)")

class SearchResult(BaseModel):
    chunk_id: str
    doc_id: str
    filename: str
    page_number: int
    chunk_index: int
    score: float = Field(..., description="Cosine similarity score (0.0 to 1.0)")
    text: str
    start_char: int
    end_char: int
    boundary_type: str
    is_approximate: bool
    word_count: int
    char_count: int = 0

class SearchResponse(BaseModel):
    query: str
    total_results: int
    results: List[SearchResult]
    search_time_ms: float
    latency_ms: float = 0.0
    model: str
    model_name: str = ""
    message: str = "Search completed successfully"

class IndexStatsResponse(BaseModel):
    total_documents: int
    total_chunks: int
    total_vectors: int
    dimension: int
    embedding_model: str
    model_license: str
    index_type: str
    memory_usage_mb: float
    status: str
