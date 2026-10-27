from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class DocumentPage(BaseModel):
    page_number: int = Field(..., description="1-indexed page or logical section number")
    text: str = Field(..., description="Extracted textual content for this page")
    char_count: int = Field(..., description="Character count on this page")
    word_count: int = Field(..., description="Word count on this page")

class DocumentExtractionResponse(BaseModel):
    success: bool = True
    filename: str
    file_type: str
    file_size_bytes: int
    file_size_formatted: str
    total_pages: int
    total_characters: int
    total_words: int
    preview_text: str
    extracted_pages: List[DocumentPage]
    metadata: Dict[str, Any] = Field(default_factory=dict)
    message: str = "Document processed successfully"

class ValidationResult(BaseModel):
    is_valid: bool
    filename: str
    file_type: str
    file_size_bytes: int
    error: Optional[str] = None

class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    environment: str
    max_upload_size_mb: int
    supported_formats: List[str]
