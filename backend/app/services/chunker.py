import re
from typing import List, Tuple
from app.schemas.document import DocumentPage
from app.schemas.chunk import ChunkRecord

def split_into_semantic_units(text: str) -> List[Tuple[str, int, int]]:
    """
    Split text into granular semantic units (paragraphs or sentences)
    while recording exact (start_char, end_char) offsets in the source text.
    """
    if not text:
        return []

    # First attempt splitting by double newlines (paragraphs)
    paragraphs = []
    # Pattern to match paragraphs and their spans
    for match in re.finditer(r'[^\n]+(?:\n[^\n]+)*', text):
        raw_para = match.group(0)
        p_start = match.start()
        p_end = match.end()
        
        # Clean leading/trailing spaces while adjusting offsets
        stripped = raw_para.strip()
        if not stripped:
            continue
        offset_start = p_start + raw_para.find(stripped)
        offset_end = offset_start + len(stripped)
        paragraphs.append((stripped, offset_start, offset_end))

    # If paragraph splitting yields no items, fall back to entire text
    if not paragraphs:
        return [(text.strip(), 0, len(text.strip()))]

    # Now inspect paragraphs: if any paragraph exceeds 400 chars, subdivide into sentences
    units = []
    for para_text, p_start, p_end in paragraphs:
        if len(para_text) <= 400:
            units.append((para_text, p_start, p_end))
        else:
            # Sentence split with lookbehind for punctuation
            sent_matches = list(re.finditer(r'[^.!?]+(?:[.!?]+|$)', para_text))
            if len(sent_matches) <= 1:
                units.append((para_text, p_start, p_end))
            else:
                for sm in sent_matches:
                    s_raw = sm.group(0)
                    s_clean = s_raw.strip()
                    if s_clean:
                        rel_start = sm.start() + s_raw.find(s_clean)
                        units.append((s_clean, p_start + rel_start, p_start + rel_start + len(s_clean)))

    return units

def chunk_page_text(
    text: str,
    chunk_size: int = 500,
    chunk_overlap: int = 80
) -> List[Tuple[str, int, int]]:
    """
    Produces overlapping semantic chunks for a single page text.
    Returns: List of (chunk_text, start_char, end_char)
    """
    clean_text = text.strip()
    if not clean_text:
        return []

    # If text is already smaller than or equal to chunk_size, return it as single chunk
    if len(clean_text) <= chunk_size:
        start = text.find(clean_text)
        return [(clean_text, start, start + len(clean_text))]

    units = split_into_semantic_units(text)
    if not units:
        return []

    chunks: List[Tuple[str, int, int]] = []
    current_units: List[Tuple[str, int, int]] = []
    current_length = 0

    for unit_text, u_start, u_end in units:
        unit_len = len(unit_text)

        # If adding this unit exceeds chunk_size and we already have units accumulated
        if current_units and (current_length + unit_len + 1 > chunk_size):
            # Finalize current chunk
            first_unit = current_units[0]
            last_unit = current_units[-1]
            chunk_str = text[first_unit[1]:last_unit[2]].strip()
            if chunk_str:
                chunks.append((chunk_str, first_unit[1], last_unit[2]))

            # Compute overlap: keep trailing units up to chunk_overlap characters
            overlap_units: List[Tuple[str, int, int]] = []
            overlap_len = 0
            for prev_u in reversed(current_units):
                if overlap_len + len(prev_u[0]) <= chunk_overlap:
                    overlap_units.insert(0, prev_u)
                    overlap_len += len(prev_u[0]) + 1
                else:
                    break

            current_units = overlap_units
            current_length = sum(len(u[0]) for u in current_units) + max(0, len(current_units) - 1)

        current_units.append((unit_text, u_start, u_end))
        current_length += unit_len + 1

    # Final trailing chunk
    if current_units:
        first_unit = current_units[0]
        last_unit = current_units[-1]
        chunk_str = text[first_unit[1]:last_unit[2]].strip()
        if chunk_str:
            # Avoid exact duplicate of the last chunk
            if not chunks or chunks[-1][0] != chunk_str:
                chunks.append((chunk_str, first_unit[1], last_unit[2]))

    # Fallback if somehow chunks were empty
    if not chunks and clean_text:
        start = text.find(clean_text)
        chunks.append((clean_text, start, start + len(clean_text)))

    return chunks

def chunk_document_pages(
    doc_id: str,
    filename: str,
    pages: List[DocumentPage],
    chunk_size: int = 500,
    chunk_overlap: int = 80
) -> List[ChunkRecord]:
    """
    Chunks a list of DocumentPages into ChunkRecords while preserving:
    - document ID
    - 1-indexed page number
    - source text offsets (start_char, end_char)
    - boundary type & approximate-page metadata
    - deterministic chunk ID
    """
    all_chunks: List[ChunkRecord] = []
    chunk_counter = 0

    for page in pages:
        page_text = page.text or ""
        if not page_text.strip():
            continue

        raw_chunks = chunk_page_text(page_text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        for c_text, start_char, end_char in raw_chunks:
            chunk_id = f"{doc_id}_p{page.page_number}_c{chunk_counter}"
            all_chunks.append(
                ChunkRecord(
                    chunk_id=chunk_id,
                    doc_id=doc_id,
                    filename=filename,
                    page_number=page.page_number,
                    chunk_index=chunk_counter,
                    start_char=start_char,
                    end_char=end_char,
                    boundary_type=page.boundary_type,
                    is_approximate=page.is_approximate,
                    text=c_text,
                    char_count=len(c_text),
                    word_count=len(c_text.split())
                )
            )
            chunk_counter += 1

    return all_chunks
