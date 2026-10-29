import io
import re
from typing import List, Dict, Any, Tuple
from datetime import datetime, timezone
import pypdf
import docx
from app.schemas.document import DocumentPage, DocumentExtractionResponse
from app.services.validator import format_file_size

def clean_extracted_text(text: str) -> str:
    """Normalize whitespace and remove non-printable control characters."""
    if not text:
        return ""
    # Replace carriage returns and excessive tabs
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Clean control characters except tab and newline
    text = re.sub(r'[\x00-\x08\x0b\x0e-\x1f\x7f]', '', text)
    # Collapse multiple consecutive empty lines to maximum 2
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def extract_from_pdf(content: bytes) -> Tuple[List[DocumentPage], Dict[str, Any]]:
    """
    Extract text and metadata from PDF bytes page by page.
    Preserves 1-indexed page references.
    """
    reader = pypdf.PdfReader(io.BytesIO(content))
    total_pdf_pages = len(reader.pages)
    extracted_pages: List[DocumentPage] = []

    for idx, page in enumerate(reader.pages, start=1):
        raw_text = page.extract_text() or ""
        cleaned = clean_extracted_text(raw_text)
        words = len(cleaned.split()) if cleaned else 0
        extracted_pages.append(
            DocumentPage(
                page_number=idx,
                text=cleaned,
                char_count=len(cleaned),
                word_count=words,
                is_approximate=False,
                boundary_type="physical",
            )
        )

    # Extract metadata safely
    raw_meta = reader.metadata
    metadata: Dict[str, Any] = {
        "format": "PDF",
        "total_pdf_pages": total_pdf_pages,
        "is_encrypted": reader.is_encrypted,
    }
    if raw_meta is not None:
        title = getattr(raw_meta, "title", None) or (raw_meta.get("/Title") if hasattr(raw_meta, "get") else None)
        if title:
            metadata["title"] = str(title)
        author = getattr(raw_meta, "author", None) or (raw_meta.get("/Author") if hasattr(raw_meta, "get") else None)
        if author:
            metadata["author"] = str(author)
        creator = getattr(raw_meta, "creator", None) or (raw_meta.get("/Creator") if hasattr(raw_meta, "get") else None)
        if creator:
            metadata["creator"] = str(creator)
        producer = getattr(raw_meta, "producer", None) or (raw_meta.get("/Producer") if hasattr(raw_meta, "get") else None)
        if producer:
            metadata["producer"] = str(producer)

    return extracted_pages, metadata

def extract_from_docx(content: bytes) -> Tuple[List[DocumentPage], Dict[str, Any]]:
    """
    Extract text and properties from DOCX bytes.
    Detects page breaks (<w:br w:type="page"/>) and chunks logical sections.
    """
    doc = docx.Document(io.BytesIO(content))
    pages_text: List[List[str]] = [[]]

    for p in doc.paragraphs:
        # Check XML for explicit page breaks
        p_xml = p._p.xml if hasattr(p, '_p') and p._p is not None else ""
        if 'w:type="page"' in p_xml or 'w:lastRenderedPageBreak' in p_xml:
            # Advance page
            if pages_text[-1]:
                pages_text.append([])
        
        text = p.text.strip()
        if text:
            pages_text[-1].append(text)

    # Also capture table contents if present
    for table in doc.tables:
        table_rows = []
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            if cells:
                table_rows.append(" | ".join(cells))
        if table_rows:
            pages_text[-1].append("\n[Table Content]\n" + "\n".join(table_rows))

    # Convert to DocumentPage list
    extracted_pages: List[DocumentPage] = []
    page_num = 1
    has_explicit_breaks = len(pages_text) > 1

    for p_lines in pages_text:
        combined = "\n\n".join(p_lines)
        cleaned = clean_extracted_text(combined)
        
        # If a single section is huge (> 3500 chars), subdivide logically for better readability
        if len(cleaned) > 3500:
            words = cleaned.split()
            chunk_size = 400
            for i in range(0, len(words), chunk_size):
                sub_chunk = " ".join(words[i:i + chunk_size])
                extracted_pages.append(
                    DocumentPage(
                        page_number=page_num,
                        text=sub_chunk,
                        char_count=len(sub_chunk),
                        word_count=len(sub_chunk.split()),
                        is_approximate=True,
                        boundary_type="approximate_section",
                    )
                )
                page_num += 1
        else:
            extracted_pages.append(
                DocumentPage(
                    page_number=page_num,
                    text=cleaned,
                    char_count=len(cleaned),
                    word_count=len(cleaned.split()) if cleaned else 0,
                    is_approximate=not has_explicit_breaks,
                    boundary_type="explicit_break" if has_explicit_breaks else "approximate_section",
                )
            )
            page_num += 1

    # Extract core properties
    metadata: Dict[str, Any] = {
        "format": "DOCX",
        "has_explicit_page_breaks": has_explicit_breaks,
    }
    try:
        props = doc.core_properties
        if props.title:
            metadata["title"] = props.title
        if props.author:
            metadata["author"] = props.author
        if props.created:
            metadata["created"] = props.created.isoformat()
        if props.revision:
            metadata["revision"] = props.revision
    except Exception:
        pass

    return extracted_pages, metadata

def extract_from_txt(content: bytes) -> Tuple[List[DocumentPage], Dict[str, Any]]:
    """
    Extract text from TXT bytes.
    Splits by form feed ('\\x0c' / '\\f') page breaks or logical ~400 word chunks.
    """
    try:
        raw_text = content.decode("utf-8")
        encoding = "utf-8"
    except UnicodeDecodeError:
        raw_text = content.decode("latin-1")
        encoding = "latin-1"

    # Check for ASCII Form Feed page delimiter
    has_form_feed = "\x0c" in raw_text
    if has_form_feed:
        raw_pages = raw_text.split("\x0c")
    else:
        # Clean first
        cleaned_full = clean_extracted_text(raw_text)
        words = cleaned_full.split()
        if len(words) > 500:
            # Chunk logically by 400 words per page
            chunk_size = 400
            raw_pages = [" ".join(words[i:i + chunk_size]) for i in range(0, len(words), chunk_size)]
        else:
            raw_pages = [cleaned_full]

    extracted_pages: List[DocumentPage] = []
    for idx, page_str in enumerate(raw_pages, start=1):
        cleaned = clean_extracted_text(page_str)
        words = len(cleaned.split()) if cleaned else 0
        extracted_pages.append(
            DocumentPage(
                page_number=idx,
                text=cleaned,
                char_count=len(cleaned),
                word_count=words,
                is_approximate=not has_form_feed,
                boundary_type="form_feed" if has_form_feed else "approximate_chunk",
            )
        )

    metadata: Dict[str, Any] = {
        "format": "TXT",
        "encoding": encoding,
        "has_form_feed_delimiters": has_form_feed,
    }

    return extracted_pages, metadata

def process_document(filename: str, file_type: str, content: bytes) -> DocumentExtractionResponse:
    """
    Unified extraction pipeline for supported document formats.
    """
    if file_type == "pdf":
        pages, meta = extract_from_pdf(content)
    elif file_type == "docx":
        pages, meta = extract_from_docx(content)
    elif file_type == "txt":
        pages, meta = extract_from_txt(content)
    else:
        raise ValueError(f"Unsupported file type: {file_type}")

    total_chars = sum(p.char_count for p in pages)
    total_words = sum(p.word_count for p in pages)
    
    # Generate clean preview excerpt
    all_text = " ".join(p.text for p in pages if p.text).strip()
    preview = all_text[:400] + ("..." if len(all_text) > 400 else "")

    meta["processed_at"] = datetime.now(timezone.utc).isoformat()

    # Identify whether this is sample / demo document
    name_lower = filename.lower()
    is_sample = (
        "sample" in name_lower
        or "quarterly_executive_summary" in name_lower
        or "comprehensive_ml_research_report" in name_lower
        or meta.get("is_sample", False)
    )

    return DocumentExtractionResponse(
        success=True,
        filename=filename,
        file_type=file_type.upper(),
        file_size_bytes=len(content),
        file_size_formatted=format_file_size(len(content)),
        total_pages=len(pages),
        total_characters=total_chars,
        total_words=total_words,
        preview_text=preview,
        extracted_pages=pages,
        metadata=meta,
        is_sample=is_sample,
        message=f"Successfully extracted {len(pages)} page(s) and {total_words} word(s)."
    )
