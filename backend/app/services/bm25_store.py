"""
BM25 Lexical Retrieval Store
=============================
Parallel lexical index that complements the FAISS dense vector store.
Uses the rank_bm25 library (MIT License) for Okapi BM25 scoring.

Responsibilities:
- Maintain a BM25 corpus aligned with the vector store chunk registry
- Support per-document add / delete / rebuild without stale results
- Persist tokenized corpus + chunk ID mapping to disk
- Return ranked chunk IDs with BM25 scores for fusion with dense results
"""

import os
import re
import json
import threading
import logging
from typing import List, Dict, Optional, Tuple

import math
from rank_bm25 import BM25Okapi
from app.config import settings

logger = logging.getLogger(__name__)


class RobustBM25Okapi(BM25Okapi):
    """
    BM25Okapi variant using the Lucene/Robertson non-negative IDF formula:
    idf(t) = ln(1 + (N - n(t) + 0.5) / (n(t) + 0.5)).

    Standard rank_bm25.BM25Okapi produces 0 or negative IDF when corpus size is
    small (e.g. N <= 2 or when terms appear in half or more docs), resulting in
    zero scores. This Lucene adaptation guarantees strictly positive IDF for all
    indexed terms across any corpus size.
    """

    def _calc_idf(self, nd):
        for word, freq in nd.items():
            self.idf[word] = math.log(1.0 + (self.corpus_size - freq + 0.5) / (freq + 0.5))

# Simple tokenizer: lowercase, split on non-alphanumeric, filter short tokens
_TOKEN_RE = re.compile(r"[a-z0-9]+(?:\.[a-z0-9]+)*", re.IGNORECASE)

# Minimal English stopwords to improve BM25 precision without heavy dependencies
_STOP_WORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "it", "as", "be", "was", "were",
    "been", "are", "this", "that", "which", "who", "whom", "what", "will",
    "can", "do", "does", "did", "has", "have", "had", "not", "no", "nor",
    "so", "if", "then", "than", "too", "very", "just", "about", "up",
})


def tokenize(text: str) -> List[str]:
    """
    Lightweight tokenizer for BM25 indexing.
    Preserves identifiers, dates, clause numbers, and technical terms.
    Removes minimal stopwords to keep domain vocabulary intact.
    """
    if not text:
        return []
    tokens = _TOKEN_RE.findall(text.lower())
    # Keep tokens of length >= 1; only remove stopwords for tokens with len >= 2
    return [t for t in tokens if t not in _STOP_WORDS or len(t) <= 1]


class BM25Store:
    """
    Thread-safe BM25 lexical index with disk persistence.
    Aligned with the VectorStore chunk registry via chunk_id keys.
    """

    def __init__(self, data_dir: Optional[str] = None):
        self._lock = threading.RLock()
        self.data_dir = data_dir or settings.active_data_dir
        self.persistence_file = os.path.join(self.data_dir, "bm25_corpus.json")

        # Core data structures
        # Ordered lists: each index i corresponds across all three lists
        self._corpus: List[List[str]] = []      # tokenized documents
        self._chunk_ids: List[str] = []          # chunk_id at each position
        self._doc_ids: List[str] = []            # doc_id at each position

        # Reverse lookup: doc_id -> set of corpus positions
        self._doc_positions: Dict[str, List[int]] = {}

        # BM25 index (rebuilt on any mutation)
        self._bm25: Optional[BM25Okapi] = None

        # Attempt to load persisted state
        self._load_from_disk()

    # ─── Persistence ────────────────────────────────────────────────

    def _ensure_data_dir(self):
        os.makedirs(self.data_dir, exist_ok=True)

    def _save_to_disk(self):
        """Persist corpus, chunk IDs, and doc IDs to a JSON file."""
        try:
            self._ensure_data_dir()
            payload = {
                "corpus": self._corpus,
                "chunk_ids": self._chunk_ids,
                "doc_ids": self._doc_ids,
            }
            with open(self.persistence_file, "w", encoding="utf-8") as f:
                json.dump(payload, f)
            logger.info(
                "Persisted BM25 corpus (%d entries, %d unique docs)",
                len(self._chunk_ids),
                len(self._doc_positions),
            )
        except Exception as exc:
            logger.warning("Failed to persist BM25 corpus: %s", exc)

    def _load_from_disk(self):
        """Restore BM25 corpus from disk if available."""
        if os.path.exists(self.persistence_file):
            try:
                with open(self.persistence_file, "r", encoding="utf-8") as f:
                    payload = json.load(f)
                self._corpus = payload.get("corpus", [])
                self._chunk_ids = payload.get("chunk_ids", [])
                self._doc_ids = payload.get("doc_ids", [])
                self._rebuild_doc_positions()
                self._rebuild_bm25()
                logger.info(
                    "Loaded BM25 corpus from disk: %d entries", len(self._chunk_ids)
                )
            except Exception as exc:
                logger.warning("Could not restore BM25 corpus, starting empty: %s", exc)
                self._reset_state()

    def _reset_state(self):
        self._corpus = []
        self._chunk_ids = []
        self._doc_ids = []
        self._doc_positions = {}
        self._bm25 = None

    def _rebuild_doc_positions(self):
        """Rebuild the doc_id -> positions reverse index."""
        self._doc_positions = {}
        for idx, doc_id in enumerate(self._doc_ids):
            self._doc_positions.setdefault(doc_id, []).append(idx)

    def _rebuild_bm25(self):
        """Reconstruct the BM25Okapi index from the current corpus."""
        if self._corpus:
            self._bm25 = RobustBM25Okapi(self._corpus)
        else:
            self._bm25 = None

    # ─── Index Mutation ─────────────────────────────────────────────

    def add_chunks(
        self, doc_id: str, chunk_ids: List[str], chunk_texts: List[str]
    ) -> int:
        """
        Add tokenized chunk texts to the BM25 corpus.
        Returns the number of entries added.
        """
        if not chunk_ids or not chunk_texts:
            return 0

        with self._lock:
            # Remove any prior entries for this doc_id (handles re-uploads)
            self._remove_doc_entries(doc_id)

            tokenized = [tokenize(text) for text in chunk_texts]
            start_pos = len(self._corpus)

            self._corpus.extend(tokenized)
            self._chunk_ids.extend(chunk_ids)
            self._doc_ids.extend([doc_id] * len(chunk_ids))

            positions = list(range(start_pos, start_pos + len(chunk_ids)))
            self._doc_positions[doc_id] = positions

            self._rebuild_bm25()
            self._save_to_disk()
            return len(chunk_ids)

    def remove_document(self, doc_id: str) -> bool:
        """
        Remove all corpus entries for a document and rebuild the BM25 index.
        Returns True if entries were removed.
        """
        with self._lock:
            return self._remove_doc_entries(doc_id, persist=True)

    def _remove_doc_entries(self, doc_id: str, persist: bool = False) -> bool:
        """Internal: remove entries for a doc_id and optionally persist."""
        if doc_id not in self._doc_positions:
            return False

        positions_to_remove = set(self._doc_positions.pop(doc_id))

        # Rebuild lists excluding removed positions
        new_corpus = []
        new_chunk_ids = []
        new_doc_ids = []
        for idx in range(len(self._corpus)):
            if idx not in positions_to_remove:
                new_corpus.append(self._corpus[idx])
                new_chunk_ids.append(self._chunk_ids[idx])
                new_doc_ids.append(self._doc_ids[idx])

        self._corpus = new_corpus
        self._chunk_ids = new_chunk_ids
        self._doc_ids = new_doc_ids

        self._rebuild_doc_positions()
        self._rebuild_bm25()

        if persist:
            self._save_to_disk()
        return True

    def clear_all(self):
        """Clear all BM25 data."""
        with self._lock:
            self._reset_state()
            if os.path.exists(self.persistence_file):
                os.remove(self.persistence_file)

    # ─── Search ─────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        top_k: int = 20,
        doc_id: Optional[str] = None,
    ) -> List[Tuple[str, float]]:
        """
        Search the BM25 index and return ranked (chunk_id, score) tuples.
        Returns up to top_k results. If doc_id is specified, only chunks
        from that document are considered.
        """
        with self._lock:
            if not self._bm25 or not self._corpus:
                return []

            query_tokens = tokenize(query)
            if not query_tokens:
                return []

            scores = self._bm25.get_scores(query_tokens)

            # Build (index, score) pairs
            scored_indices = list(enumerate(scores))

            # Filter by document if requested
            if doc_id:
                valid_positions = set(self._doc_positions.get(doc_id, []))
                scored_indices = [
                    (idx, s) for idx, s in scored_indices if idx in valid_positions
                ]

            # Sort by score descending
            scored_indices.sort(key=lambda x: x[1], reverse=True)

            # Filter zero-score results and take top_k
            results = []
            for idx, score in scored_indices[:top_k]:
                if score <= 0.0:
                    break
                results.append((self._chunk_ids[idx], float(score)))

            return results

    # ─── Stats ──────────────────────────────────────────────────────

    def get_stats(self) -> Dict:
        with self._lock:
            avg_doc_len = 0.0
            if self._bm25 and hasattr(self._bm25, "avgdl"):
                avg_doc_len = round(self._bm25.avgdl, 1)
            return {
                "total_entries": len(self._corpus),
                "unique_documents": len(self._doc_positions),
                "avg_document_length_tokens": avg_doc_len,
                "algorithm": "BM25Okapi (rank_bm25)",
                "license": "MIT",
            }


# Module-level singleton
bm25_store = BM25Store()
