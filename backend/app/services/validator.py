import os
import re
import zipfile
import io
from typing import Tuple
from fastapi import UploadFile, HTTPException, status
from app.config import settings

def sanitize_filename(filename: str) -> str:
    """
    Sanitize uploaded filename to prevent directory traversal, control characters,
    and injection attacks.
    """
    if not filename:
        return "unnamed_document.txt"
    # Extract only the base name (strip any path components)
    basename = os.path.basename(filename.strip().replace("\\", "/"))
    # Remove null bytes and dangerous characters
    clean_name = re.sub(r'[^\w\-_\. ()]', '_', basename)
    # Avoid names starting with dots or being empty
    clean_name = clean_name.lstrip(".")
    if not clean_name:
        return "unnamed_document.txt"
    # Limit max length
    if len(clean_name) > 120:
        name_part, ext_part = os.path.splitext(clean_name)
        clean_name = name_part[:120 - len(ext_part)] + ext_part
    return clean_name

def format_file_size(size_in_bytes: int) -> str:
    """Convert bytes to human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_in_bytes < 1024.0:
            return f"{size_in_bytes:.1f} {unit}" if unit != 'B' else f"{size_in_bytes} B"
        size_in_bytes /= 1024.0
    return f"{size_in_bytes:.1f} TB"

async def validate_and_read_upload(file: UploadFile) -> Tuple[str, str, bytes]:
    """
    Validates the uploaded file:
    1. Checks filename and allowed extension (.pdf, .docx, .txt)
    2. Validates file size safely with chunking against MAX_UPLOAD_SIZE_BYTES
    3. Validates file integrity and magic byte signatures
    4. Guarantees temporary file cleanup on disk via await file.close() in finally block
    Returns: (safe_filename, file_type, file_content_bytes)
    """
    try:
        raw_filename = file.filename or ""
        safe_name = sanitize_filename(raw_filename)
        _, ext = os.path.splitext(safe_name.lower())

        if ext not in settings.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type '{ext}'. Supported formats are: {', '.join(sorted(settings.ALLOWED_EXTENSIONS))}"
            )

        # Read content with size check in chunks to prevent memory denial-of-service
        chunk_size = 64 * 1024  # 64KB
        total_read = 0
        buffer = io.BytesIO()

        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            total_read += len(chunk)
            if total_read > settings.MAX_UPLOAD_SIZE_BYTES:
                raise HTTPException(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    detail=f"File exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_MB}MB."
                )
            buffer.write(chunk)

        if total_read == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The uploaded file is empty (0 bytes)."
            )

        content = buffer.getvalue()

        # Validate file signatures
        if ext == ".pdf":
            if not content.startswith(b"%PDF-"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid PDF file format. Missing standard PDF file header."
                )
            file_type = "pdf"

        elif ext == ".docx":
            # Check standard ZIP archive magic numbers PK\x03\x04
            if not content.startswith(b"PK\x03\x04"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid DOCX file format. Expected OpenXML ZIP archive header."
                )
            try:
                with zipfile.ZipFile(io.BytesIO(content)) as zf:
                    # Protection against zip-bomb decompression attacks
                    total_uncompressed = sum(info.file_size for info in zf.infolist())
                    if total_uncompressed > settings.MAX_UPLOAD_SIZE_BYTES * 5:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Corrupted or dangerous DOCX: uncompressed archive ratio exceeds safety threshold."
                        )

                    # DOCX standard requirement: word/document.xml or [Content_Types].xml
                    namelist = zf.namelist()
                    if not any("word/document.xml" in name for name in namelist) and "[Content_Types].xml" not in namelist:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Corrupted DOCX archive: missing internal document structure."
                        )
            except zipfile.BadZipFile:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Corrupted DOCX file: unable to read ZIP archive structure."
                )
            file_type = "docx"

        elif ext == ".txt":
            # Check text decodability and reject binary executable or null bytes
            try:
                # Check first 4KB for null bytes (indicative of binary/compiled payload)
                if b"\x00" in content[:4096]:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid TXT file: binary data or null bytes detected."
                    )
                # Try decoding sample
                content[:4096].decode("utf-8")
            except UnicodeDecodeError:
                try:
                    content[:4096].decode("latin-1")
                except Exception:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid TXT file: text encoding could not be determined (must be UTF-8 or Latin-1)."
                    )
            file_type = "txt"

        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported format: {ext}"
            )

        return safe_name, file_type, content
    finally:
        # Guarantee closure and prompt cleanup of underlying SpooledTemporaryFile on disk
        try:
            await file.close()
        except Exception:
            pass
