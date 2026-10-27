import os
from fastapi import APIRouter, UploadFile, File, HTTPException, status
from app.config import settings
from app.services.validator import validate_and_read_upload, format_file_size, sanitize_filename
from app.services.extractor import process_document
from app.schemas.document import DocumentExtractionResponse, ValidationResult

router = APIRouter(prefix="/api/documents", tags=["Documents"])

@router.post("/upload", response_model=DocumentExtractionResponse)
async def upload_document(file: UploadFile = File(...)):
    """
    Upload and process a document (PDF, DOCX, or TXT).
    Validates file integrity, enforces size limits, and performs initial text extraction
    with page reference preservation.
    """
    try:
        safe_name, file_type, content = await validate_and_read_upload(file)
        result = process_document(safe_name, file_type, content)
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while processing the document: {str(exc)}"
        )

@router.post("/validate", response_model=ValidationResult)
async def validate_document_endpoint(file: UploadFile = File(...)):
    """
    Validates a document without running the full text extraction pipeline.
    """
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

@router.get("/supported-types")
async def get_supported_types():
    """
    Returns supported file extensions and upload constraints.
    """
    return {
        "allowed_extensions": sorted(list(settings.ALLOWED_EXTENSIONS)),
        "allowed_mime_types": sorted(list(settings.ALLOWED_MIME_TYPES)),
        "max_upload_size_mb": settings.MAX_UPLOAD_SIZE_MB,
        "max_upload_size_bytes": settings.MAX_UPLOAD_SIZE_BYTES
    }
