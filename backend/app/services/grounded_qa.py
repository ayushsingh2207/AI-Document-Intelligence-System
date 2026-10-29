"""
Grounded Question Answering Service
=====================================
Extracts grounded, evidence-backed answers from uploaded document passages
using the existing hybrid retrieval pipeline (Dense FAISS + BM25Okapi + RRF),
calibrated sentence-level semantic scoring, and conservative abstention.

Zero paid APIs, zero heavy LLM dependencies, zero leakage into CUAD experiments.
"""

import re
import time
import logging
from typing import List, Dict, Any, Optional, Set, Tuple
import numpy as np

from app.schemas.chunk import SearchResult
from app.schemas.qa import Citation, QARequest, QAResponse
from app.services.hybrid_retriever import HybridRetriever, RetrievalStrategy
from app.services.embedding_service import EmbeddingService, embedding_service
from app.services.vector_store import VectorStore

logger = logging.getLogger(__name__)

# Standard English functional stopwords to isolate meaningful content terms
STOP_WORDS: Set[str] = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "can't", "cannot", "could",
    "couldn't", "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down",
    "during", "each", "few", "for", "from", "further", "had", "hadn't", "has",
    "hasn't", "have", "haven't", "having", "he", "her", "here", "hers", "herself",
    "him", "himself", "his", "how", "i", "if", "in", "into", "is", "isn't", "it",
    "its", "itself", "me", "more", "most", "must", "my", "myself", "no", "nor",
    "not", "of", "off", "on", "once", "only", "or", "other", "ought", "our", "ours",
    "ourselves", "out", "over", "own", "same", "she", "should", "shouldn't", "so",
    "some", "such", "than", "that", "the", "their", "theirs", "them", "themselves",
    "then", "there", "these", "they", "this", "those", "through", "to", "too",
    "under", "until", "up", "very", "was", "wasn't", "we", "were", "weren't", "what",
    "when", "where", "which", "while", "who", "whom", "why", "with", "would",
    "you", "your", "yours", "yourself", "yourselves"
}


def extract_content_terms(text: str) -> Set[str]:
    """Extract alphanumeric tokens lowercased, filtering out English stopwords and 1-letter noise."""
    tokens = re.findall(r"\b[a-zA-Z0-9_\-\$]+\b", text.lower())
    return {t for t in tokens if t not in STOP_WORDS and len(t) > 1}


COMMON_ABBREVIATIONS: Set[str] = {
    "dr", "mr", "mrs", "ms", "prof", "inc", "corp", "llc", "ltd", "co",
    "sec", "no", "vs", "eg", "ie", "al", "jan", "feb", "mar", "apr",
    "jun", "jul", "aug", "sep", "oct", "nov", "dec"
}


def split_into_sentences(text: str) -> List[Tuple[str, int, int]]:
    """
    Split text into sentences while calculating exact start and end character offsets within text.
    Handles abbreviations (Dr., Inc., etc.) without splitting mid-sentence.
    Returns: List of (sentence_text, start_char, end_char)
    """
    sentences: List[Tuple[str, int, int]] = []
    if not text or not text.strip():
        return sentences

    raw_splits = list(re.finditer(r"(?:(?<=[.!?])\s+(?=[A-Z0-9\(\"\'\[])|\n\s*\n+)", text))

    last_idx = 0
    for match in raw_splits:
        split_start = match.start()
        split_end = match.end()

        # Check if preceding token is an abbreviation
        prefix = text[last_idx:split_start].rstrip(".!?")
        words = prefix.split()
        last_word = words[-1].lower() if words else ""

        if last_word in COMMON_ABBREVIATIONS or (len(last_word) == 1 and last_word.isalpha()):
            # Skip false boundary on abbreviations like Dr. or initials like A.
            continue

        candidate = text[last_idx:split_start].strip()
        if len(candidate) >= 10:
            s_start = text.find(candidate, last_idx)
            s_end = s_start + len(candidate)
            sentences.append((candidate, s_start, s_end))
            last_idx = split_end

    tail = text[last_idx:].strip()
    if len(tail) >= 10:
        s_start = text.find(tail, last_idx)
        s_end = s_start + len(tail)
        sentences.append((tail, s_start, s_end))
    elif tail and sentences:
        prev_text, prev_start, _ = sentences[-1]
        combined = text[prev_start : last_idx + len(tail)].strip()
        sentences[-1] = (combined, prev_start, prev_start + len(combined))
    elif tail and not sentences:
        s_start = text.find(tail)
        sentences.append((tail, s_start, s_start + len(tail)))

    return sentences


class GroundedQAService:
    """
    Production service orchestrating evidence retrieval, sentence-level grounding,
    concise extractive answer compilation, and conservative abstention.
    """

    DEFAULT_CONFIDENCE_THRESHOLD = 0.45

    def __init__(
        self,
        hybrid_retriever: HybridRetriever,
        vector_store: VectorStore,
        embedder: Optional[EmbeddingService] = None,
    ):
        self.hybrid_retriever = hybrid_retriever
        self.vector_store = vector_store
        self.embedder = embedder or embedding_service

    def answer_question(self, request: QARequest) -> QAResponse:
        """
        Answer a question using retrieved passage evidence with verifiable citations,
        or conservatively abstain when evidence is insufficient.
        """
        start_time = time.time()
        clean_question = request.question.strip()

        # 1. Validation: Clean question
        if not clean_question:
            return QAResponse(
                question=request.question,
                answered=False,
                answer="Question is empty. Please enter a valid inquiry.",
                confidence=0.0,
                abstention_reason="empty_query",
                citations=[],
                latency_ms=0.0,
            )

        # 2. Validation: Scoped Document Existence
        if request.doc_id:
            doc_record = self.vector_store.get_document(request.doc_id)
            if not doc_record:
                raise ValueError(f"Document with ID '{request.doc_id}' not found.")

        # 3. Check for Empty Knowledge Base
        total_chunks = len(self.vector_store._vector_to_chunk)
        if total_chunks == 0:
            elapsed_ms = round((time.time() - start_time) * 1000.0, 2)
            return QAResponse(
                question=clean_question,
                answered=False,
                answer="No documents have been indexed yet. Please upload a document first.",
                confidence=0.0,
                abstention_reason="index_empty",
                citations=[],
                latency_ms=elapsed_ms,
            )

        # 4. Hybrid Evidence Retrieval (RRF Dense + BM25)
        search_resp = self.hybrid_retriever.search(
            query=clean_question,
            top_k=request.top_k,
            doc_id=request.doc_id,
            strategy=RetrievalStrategy.HYBRID,
        )

        candidate_chunks = search_resp.results
        if not candidate_chunks:
            elapsed_ms = round((time.time() - start_time) * 1000.0, 2)
            return QAResponse(
                question=clean_question,
                answered=False,
                answer="I could not find sufficient evidence in the uploaded document(s) to answer this question.",
                confidence=0.0,
                abstention_reason="insufficient_evidence",
                citations=[],
                latency_ms=elapsed_ms,
            )

        # 5. Sentence-Level Evidence Scoring
        query_terms = extract_content_terms(clean_question)
        query_embedding = self.embedder.embed_texts([clean_question])  # shape (1, 384)

        # Collect candidate sentences across all retrieved chunks
        candidate_sentences: List[Dict[str, Any]] = []
        sentence_texts_for_batch: List[str] = []

        for chunk in candidate_chunks:
            # Enforce document scope invariant
            if request.doc_id and chunk.doc_id != request.doc_id:
                continue

            chunk_sentences = split_into_sentences(chunk.text)
            for s_text, s_start_in_chunk, s_end_in_chunk in chunk_sentences:
                # Calculate exact character offsets within source page
                page_start = chunk.start_char + s_start_in_chunk
                page_end = chunk.start_char + s_end_in_chunk

                candidate_sentences.append({
                    "sentence_text": s_text,
                    "chunk": chunk,
                    "page_start": page_start,
                    "page_end": page_end,
                })
                sentence_texts_for_batch.append(s_text)

        if not candidate_sentences:
            elapsed_ms = round((time.time() - start_time) * 1000.0, 2)
            return QAResponse(
                question=clean_question,
                answered=False,
                answer="I could not find sufficient evidence in the uploaded document(s) to answer this question.",
                confidence=0.0,
                abstention_reason="insufficient_evidence",
                citations=[],
                latency_ms=elapsed_ms,
            )

        # Batch embed candidate sentences
        sentence_embeddings = self.embedder.embed_texts(sentence_texts_for_batch)  # (N, 384)
        # Cosine similarity is dot product of normalized embeddings
        cosine_sims = np.dot(sentence_embeddings, query_embedding.T).flatten()  # (N,)

        scored_candidates = []
        for idx, item in enumerate(candidate_sentences):
            s_text = item["sentence_text"]
            sim = float(max(0.0, cosine_sims[idx]))

            sent_terms = extract_content_terms(s_text)
            overlap = len(query_terms & sent_terms) / max(1, len(query_terms)) if query_terms else 0.0

            # Grounding formula: 60% semantic similarity + 40% keyword overlap
            evidence_score = 0.60 * sim + 0.40 * overlap

            # Anchor penalty: if query has specific content keywords, zero term overlap severely penalizes confidence
            if len(query_terms) >= 2 and overlap == 0.0:
                evidence_score *= 0.50

            scored_candidates.append({
                **item,
                "semantic_sim": sim,
                "lexical_overlap": overlap,
                "evidence_score": round(evidence_score, 4),
            })

        # Rank candidate sentences descending by evidence score
        scored_candidates.sort(key=lambda x: x["evidence_score"], reverse=True)
        best_candidate = scored_candidates[0]
        best_score = best_candidate["evidence_score"]

        threshold = request.confidence_threshold or self.DEFAULT_CONFIDENCE_THRESHOLD

        # 6. Conservative Abstention Gate
        if best_score < threshold:
            elapsed_ms = round((time.time() - start_time) * 1000.0, 2)
            return QAResponse(
                question=clean_question,
                answered=False,
                answer="I could not find sufficient evidence in the uploaded document(s) to answer this question.",
                confidence=best_score,
                abstention_reason="insufficient_evidence",
                citations=[],
                retrieval_strategy=search_resp.retrieval_strategy,
                latency_ms=elapsed_ms,
            )

        # 7. Answer Construction & Citation Attribution
        selected_candidates = [best_candidate]
        seen_texts = {best_candidate["sentence_text"].lower()}

        # Optionally add a second highly supportive non-redundant sentence (score >= 0.5)
        for cand in scored_candidates[1:4]:
            if cand["evidence_score"] >= max(0.50, threshold):
                text_lower = cand["sentence_text"].lower()
                if text_lower not in seen_texts:
                    selected_candidates.append(cand)
                    seen_texts.add(text_lower)
                    break

        # Assemble answer text from supportive excerpts
        answer_text = " ".join(c["sentence_text"] for c in selected_candidates)

        citations: List[Citation] = []
        for cit_idx, cand in enumerate(selected_candidates):
            c_chunk = cand["chunk"]
            citations.append(
                Citation(
                    citation_id=f"cit_{cit_idx + 1}",
                    doc_id=c_chunk.doc_id,
                    filename=c_chunk.filename,
                    page_number=c_chunk.page_number,
                    chunk_id=c_chunk.chunk_id,
                    start_char=cand["page_start"],
                    end_char=cand["page_end"],
                    supporting_excerpt=cand["sentence_text"],
                    boundary_type=c_chunk.boundary_type,
                    is_approximate=c_chunk.is_approximate,
                    relevance_score=cand["evidence_score"],
                )
            )

        elapsed_ms = round((time.time() - start_time) * 1000.0, 2)
        return QAResponse(
            question=clean_question,
            answered=True,
            answer=answer_text,
            confidence=best_score,
            abstention_reason=None,
            citations=citations,
            retrieval_strategy=search_resp.retrieval_strategy,
            latency_ms=elapsed_ms,
        )
