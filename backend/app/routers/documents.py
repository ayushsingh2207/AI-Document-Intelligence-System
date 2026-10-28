import os
import hashlib
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, HTTPException, status, Query
from app.config import settings
from app.services.validator import validate_and_read_upload, format_file_size, sanitize_filename
from app.services.extractor import process_document
from app.services.vector_store import vector_store
from app.schemas.document import DocumentExtractionResponse, ValidationResult
from app.schemas.chunk import DocumentSummary, ChunkRecord

router = APIRouter(prefix="/api/documents", tags=["Documents"])

def generate_document_id(filename: str, content: bytes) -> str:
    """Generate a stable, unique document identifier based on content hash."""
    hasher = hashlib.sha256()
    hasher.update(filename.encode("utf-8"))
    hasher.update(content[:1024])
    hasher.update(str(len(content)).encode("utf-8"))
    return f"doc_{hasher.hexdigest()[:12]}"

@router.post("/upload", response_model=DocumentExtractionResponse)
async def upload_document(
    file: UploadFile = File(...),
    chunk_size: int = Query(default=500, ge=100, le=2000, description="Semantic chunk size in characters"),
    chunk_overlap: int = Query(default=80, ge=0, le=500, description="Semantic chunk overlap in characters")
):
    """
    Upload, validate, extract, and index a document (PDF, DOCX, or TXT).
    Phase 1: Validates file integrity, enforces size limits, and performs text extraction.
    Phase 2: Performs semantic-aware chunking, generates embeddings with all-MiniLM-L6-v2,
             and indexes vectors into FAISS.
    """
    try:
        safe_name, file_type, content = await validate_and_read_upload(file)
        
        # 1. Extraction (Phase 1)
        result = process_document(safe_name, file_type, content)
        doc_id = generate_document_id(safe_name, content)
        result.doc_id = doc_id

        # 2. Semantic Chunking & Vector Indexing (Phase 2)
        try:
            doc_summary = vector_store.index_document(
                doc_id=doc_id,
                filename=safe_name,
                file_type=file_type,
                file_size_bytes=len(content),
                pages=result.extracted_pages,
                metadata=result.metadata,
                is_sample=result.is_sample,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap
            )
            result.total_chunks = doc_summary.total_chunks
            result.message = (
                f"Successfully extracted {result.total_pages} page(s), {result.total_words} word(s), "
                f"and indexed {doc_summary.total_chunks} semantic chunk(s)."
            )
        except Exception as embed_exc:
            # If embedding fails (e.g. offline/resource issue), preserve extraction results gracefully
            result.message = f"Extracted {result.total_pages} page(s), but vector indexing encountered: {str(embed_exc)}"

        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while processing the document: {str(exc)}"
        )

@router.get("", response_model=List[DocumentSummary])
async def list_documents():
    """List all indexed documents in the vector store registry."""
    return vector_store.list_documents()

@router.get("/supported-types")
async def get_supported_types():
    """Returns supported file extensions and upload constraints."""
    return {
        "allowed_extensions": sorted(list(settings.ALLOWED_EXTENSIONS)),
        "allowed_mime_types": sorted(list(settings.ALLOWED_MIME_TYPES)),
        "max_upload_size_mb": settings.MAX_UPLOAD_SIZE_MB,
        "max_upload_size_bytes": settings.MAX_UPLOAD_SIZE_BYTES
    }

@router.post("/validate", response_model=ValidationResult)
async def validate_document_endpoint(file: UploadFile = File(...)):
    """Validates a document without running the extraction or indexing pipeline."""
    try:
        safe_name, file_type, content = await validate_and_read_upload(file)
        return ValidationResult(
            is_valid=True,
            filename=safe_name,
            file_type=file_type.upper(),
            file_size_bytes=len(content),
            error=None
        )
    except HTTPException as exc:
        raw_name = sanitize_filename(file.filename or "")
        _, ext = os.path.splitext(raw_name)
        return ValidationResult(
            is_valid=False,
            filename=raw_name,
            file_type=ext.lstrip(".").upper() or "UNKNOWN",
            file_size_bytes=0,
            error=exc.detail
        )

@router.get("/{doc_id}", response_model=DocumentSummary)
async def get_document(doc_id: str):
    """Get metadata summary for a specific document."""
    doc = vector_store.get_document(doc_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{doc_id}' not found."
        )
    return doc

@router.get("/{doc_id}/chunks", response_model=List[ChunkRecord])
async def get_document_chunks(doc_id: str):
    """Retrieve all semantic chunk records and source offsets for a document."""
    doc = vector_store.get_document(doc_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{doc_id}' not found."
        )
    return vector_store.get_document_chunks(doc_id)

@router.delete("/{doc_id}")
async def delete_document(doc_id: str):
    """Delete a document and purge its vectors from the FAISS index and metadata store."""
    deleted = vector_store.delete_document(doc_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{doc_id}' not found."
        )
    return {
        "success": True,
        "message": f"Document '{doc_id}' and all associated vector representations deleted.",
        "doc_id": doc_id
    }

