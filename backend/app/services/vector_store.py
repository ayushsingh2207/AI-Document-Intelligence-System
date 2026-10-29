import os
import json
import time
import threading
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
import numpy as np
import faiss

from app.schemas.chunk import ChunkRecord, DocumentSummary, SearchResult, SearchResponse, IndexStatsResponse
from app.schemas.document import DocumentPage
from app.config import settings
from app.services.chunker import chunk_document_pages
from app.services.embedding_service import embedding_service
from app.services.validator import format_file_size
from app.services.bm25_store import bm25_store

logger = logging.getLogger(__name__)

DATA_DIR = settings.DATA_DIR
INDEX_FILE = os.path.join(DATA_DIR, "vector_index.faiss")
METADATA_FILE = os.path.join(DATA_DIR, "metadata_store.json")

class VectorStore:
    """
    Lightweight local Vector Store powered by FAISS IndexFlatIP with
    separate metadata storage for Document and Chunk records.
    Supports multi-document queries, updates, deletions, and duplicate handling.
    """
    def __init__(self, dimension: int = 384, data_dir: Optional[str] = None, bm25_store_instance: Optional[Any] = None):
        self.dimension = dimension
        self._lock = threading.RLock()
        
        # Configure persistence directory: defaults to settings.active_data_dir
        if data_dir is not None:
            self.data_dir = data_dir
        else:
            self.data_dir = settings.active_data_dir

        self.index_file = os.path.join(self.data_dir, "vector_index.faiss") if self.data_dir else None
        self.metadata_file = os.path.join(self.data_dir, "metadata_store.json") if self.data_dir else None

        # BM25 instance: isolated if custom data_dir provided or explicit instance passed
        if bm25_store_instance is not None:
            self.bm25 = bm25_store_instance
        elif self.data_dir != DATA_DIR:
            from app.services.bm25_store import BM25Store
            self.bm25 = BM25Store(data_dir=self.data_dir)
        else:
            self.bm25 = bm25_store

        # FAISS Index for Cosine Similarity (vectors are L2-normalized)
        self._index: faiss.IndexFlatIP = faiss.IndexFlatIP(self.dimension)
        
        # Metadata storage separated from raw vectors
        # vector_id (int) -> ChunkRecord
        self._vector_to_chunk: Dict[int, ChunkRecord] = {}
        # doc_id (str) -> DocumentSummary
        self._documents: Dict[str, DocumentSummary] = {}
        # doc_id (str) -> List of vector_ids
        self._doc_to_vector_ids: Dict[str, List[int]] = {}
        # filename (lowercase) -> doc_id (for duplicate upload detection)
        self._filename_to_doc_id: Dict[str, str] = {}
        
        # Rebuilding tracking: next vector id
        self._next_vector_id = 0

        # Load persisted data if available
        if self.data_dir:
            self._load_from_disk()

    def _ensure_data_dir(self):
        if self.data_dir:
            os.makedirs(self.data_dir, exist_ok=True)

    def _save_to_disk(self):
        """Persist FAISS index and metadata store to disk."""
        if not self.data_dir or not self.index_file or not self.metadata_file:
            return
        try:
            self._ensure_data_dir()
            # Save FAISS index
            faiss.write_index(self._index, self.index_file)
            
            # Save metadata
            meta_payload = {
                "documents": {k: v.model_dump() for k, v in self._documents.items()},
                "vector_chunks": {str(k): v.model_dump() for k, v in self._vector_to_chunk.items()},
                "doc_to_vector_ids": self._doc_to_vector_ids,
                "filename_to_doc_id": self._filename_to_doc_id,
                "next_vector_id": self._next_vector_id,
            }
            with open(self.metadata_file, "w", encoding="utf-8") as f:
                json.dump(meta_payload, f, indent=2)
            logger.info("Persisted vector store (%d vectors, %d docs)", self._index.ntotal, len(self._documents))
        except Exception as exc:
            logger.warning("Failed to persist vector store to disk: %s", str(exc))

    def _load_from_disk(self):
        """Restore FAISS index and metadata store from disk if present."""
        if not self.data_dir or not self.index_file or not self.metadata_file:
            return
        if os.path.exists(self.index_file) and os.path.exists(self.metadata_file):
            try:
                self._index = faiss.read_index(self.index_file)
                with open(self.metadata_file, "r", encoding="utf-8") as f:
                    meta_payload = json.load(f)
                
                self._documents = {
                    k: DocumentSummary(**v) for k, v in meta_payload.get("documents", {}).items()
                }
                self._vector_to_chunk = {
                    int(k): ChunkRecord(**v) for k, v in meta_payload.get("vector_chunks", {}).items()
                }
                self._doc_to_vector_ids = meta_payload.get("doc_to_vector_ids", {})
                self._filename_to_doc_id = meta_payload.get("filename_to_doc_id", {})
                self._next_vector_id = meta_payload.get("next_vector_id", self._index.ntotal)
                logger.info("Loaded vector store from disk: %d vectors, %d docs", self._index.ntotal, len(self._documents))
            except Exception as exc:
                logger.warning("Could not restore persisted vector store, initializing empty: %s", str(exc))
                self.clear_all()

    def index_document(
        self,
        doc_id: str,
        filename: str,
        file_type: str,
        file_size_bytes: int,
        pages: List[DocumentPage],
        metadata: Optional[Dict[str, Any]] = None,
        is_sample: bool = False,
        chunk_size: int = 500,
        chunk_overlap: int = 80
    ) -> DocumentSummary:
        """
        Chunks, embeds, and indexes document pages into the vector store.
        Automatically updates existing document if filename or doc_id matches (duplicate handling).
        """
        with self._lock:
            # Check duplicate by doc_id or filename
            fn_key = filename.strip().lower()
            if doc_id in self._documents:
                self.delete_document(doc_id)
            elif fn_key in self._filename_to_doc_id:
                old_id = self._filename_to_doc_id[fn_key]
                self.delete_document(old_id)

            now_iso = datetime.now(timezone.utc).isoformat()
            
            # 1. Semantic Chunking
            chunks = chunk_document_pages(
                doc_id=doc_id,
                filename=filename,
                pages=pages,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap
            )

            total_words = sum(p.word_count for p in pages)
            all_text = " ".join(p.text for p in pages if p.text).strip()
            preview = all_text[:400] + ("..." if len(all_text) > 400 else "")

            doc_summary = DocumentSummary(
                doc_id=doc_id,
                filename=filename,
                file_type=file_type.upper(),
                file_size_bytes=file_size_bytes,
                file_size_formatted=format_file_size(file_size_bytes),
                total_pages=len(pages),
                total_words=total_words,
                total_chunks=len(chunks),
                preview_text=preview,
                is_sample=is_sample,
                metadata=metadata or {},
                created_at=now_iso,
                updated_at=now_iso
            )

            # If no text chunks extracted (e.g. empty or scanned document)
            if not chunks:
                self._documents[doc_id] = doc_summary
                self._filename_to_doc_id[fn_key] = doc_id
                self._doc_to_vector_ids[doc_id] = []
                self._save_to_disk()
                return doc_summary

            # 2. Embedding Generation using Sentence-Transformers
            chunk_texts = [c.text for c in chunks]
            embeddings = embedding_service.embed_texts(chunk_texts)

            # 3. Add vectors to FAISS index
            start_vid = self._next_vector_id
            self._index.add(embeddings)
            
            vector_ids = []
            for i, chunk in enumerate(chunks):
                vid = start_vid + i
                self._vector_to_chunk[vid] = chunk
                vector_ids.append(vid)

            self._next_vector_id += len(chunks)

            # 4. Update document metadata registries
            self._documents[doc_id] = doc_summary
            self._filename_to_doc_id[fn_key] = doc_id
            self._doc_to_vector_ids[doc_id] = vector_ids

            # 5. Index chunks in the parallel BM25 lexical store
            try:
                chunk_ids_list = [c.chunk_id for c in chunks]
                self.bm25.add_chunks(doc_id, chunk_ids_list, chunk_texts)
            except Exception as bm25_exc:
                logger.warning("BM25 indexing failed for doc %s (non-blocking): %s", doc_id, bm25_exc)

            self._save_to_disk()
            return doc_summary

    def delete_document(self, doc_id: str) -> bool:
        """
        Deletes a document and its chunks from metadata and rebuilds the FAISS index
        without the deleted vectors to prevent stale search results.
        """
        with self._lock:
            if doc_id not in self._documents:
                return False

            doc_summary = self._documents.pop(doc_id)
            fn_key = doc_summary.filename.strip().lower()
            if self._filename_to_doc_id.get(fn_key) == doc_id:
                del self._filename_to_doc_id[fn_key]

            deleted_vids = set(self._doc_to_vector_ids.pop(doc_id, []))
            for vid in deleted_vids:
                self._vector_to_chunk.pop(vid, None)

            # Rebuild FAISS index from remaining chunks to eliminate deleted vectors completely
            self._rebuild_index_from_remaining_chunks()

            # Remove from parallel BM25 index
            try:
                self.bm25.remove_document(doc_id)
            except Exception as bm25_exc:
                logger.warning("BM25 cleanup failed for doc %s (non-blocking): %s", doc_id, bm25_exc)

            self._save_to_disk()
            return True

    def _rebuild_index_from_remaining_chunks(self):
        """Reconstructs FAISS index with contiguous vector IDs from all remaining chunks."""
        remaining_chunks = list(self._vector_to_chunk.values())
        self._index = faiss.IndexFlatIP(self.dimension)
        self._vector_to_chunk.clear()
        self._doc_to_vector_ids = {d_id: [] for d_id in self._documents}

        if remaining_chunks:
            texts = [c.text for c in remaining_chunks]
            embeddings = embedding_service.embed_texts(texts)
            self._index.add(embeddings)

            for vid, chunk in enumerate(remaining_chunks):
                self._vector_to_chunk[vid] = chunk
                self._doc_to_vector_ids[chunk.doc_id].append(vid)

            self._next_vector_id = len(remaining_chunks)
        else:
            self._next_vector_id = 0

    def search(
        self,
        query: str,
        top_k: int = 5,
        doc_id: Optional[str] = None,
        min_score: float = 0.0
    ) -> SearchResponse:
        """
        Executes semantic similarity search over indexed chunks.
        Returns ranked results with source page references and similarity score.
        """
        start_time = time.time()
        clean_query = query.strip()
        if not clean_query:
            return SearchResponse(
                query=query,
                total_results=0,
                results=[],
                search_time_ms=0.0,
                latency_ms=0.0,
                model=embedding_service.MODEL_NAME,
                model_name=embedding_service.MODEL_NAME,
                message="Query was empty"
            )

        with self._lock:
            total_vectors = self._index.ntotal
            if total_vectors == 0:
                elapsed_ms = (time.time() - start_time) * 1000.0
                round_ms = round(elapsed_ms, 2)
                return SearchResponse(
                    query=clean_query,
                    total_results=0,
                    results=[],
                    search_time_ms=round_ms,
                    latency_ms=round_ms,
                    model=embedding_service.MODEL_NAME,
                    model_name=embedding_service.MODEL_NAME,
                    message="Index is empty. Upload and index documents to enable search."
                )

            # 1. Embed query
            query_vector = embedding_service.embed_query(clean_query)

            # 2. Query FAISS index for top candidates
            # Fetch a larger candidate pool if filtering by doc_id
            search_k = min(total_vectors, max(top_k * 4, 20))
            scores, indices = self._index.search(query_vector, search_k)

            results: List[SearchResult] = []
            for score, vid in zip(scores[0], indices[0]):
                if vid == -1 or vid not in self._vector_to_chunk:
                    continue

                chunk = self._vector_to_chunk[vid]

                # Document filter if requested
                if doc_id and chunk.doc_id != doc_id:
                    continue

                # Clamp and threshold score
                norm_score = float(score)
                if norm_score < min_score:
                    continue

                results.append(
                    SearchResult(
                        chunk_id=chunk.chunk_id,
                        doc_id=chunk.doc_id,
                        filename=chunk.filename,
                        page_number=chunk.page_number,
                        chunk_index=chunk.chunk_index,
                        score=round(norm_score, 4),
                        text=chunk.text,
                        start_char=chunk.start_char,
                        end_char=chunk.end_char,
                        boundary_type=chunk.boundary_type,
                        is_approximate=chunk.is_approximate,
                        word_count=chunk.word_count,
                        char_count=chunk.char_count
                    )
                )

                if len(results) >= top_k:
                    break

            elapsed_ms = (time.time() - start_time) * 1000.0
            round_ms = round(elapsed_ms, 2)
            return SearchResponse(
                query=clean_query,
                total_results=len(results),
                results=results,
                search_time_ms=round_ms,
                latency_ms=round_ms,
                model=embedding_service.MODEL_NAME,
                model_name=embedding_service.MODEL_NAME,
                message=f"Found {len(results)} matching chunk(s)"
            )

    def list_documents(self) -> List[DocumentSummary]:
        """List all indexed documents sorted by updated_at descending."""
        with self._lock:
            docs = list(self._documents.values())
            docs.sort(key=lambda d: d.updated_at, reverse=True)
            return docs

    def get_document(self, doc_id: str) -> Optional[DocumentSummary]:
        with self._lock:
            return self._documents.get(doc_id)

    def get_document_chunks(self, doc_id: str) -> List[ChunkRecord]:
        with self._lock:
            vids = self._doc_to_vector_ids.get(doc_id, [])
            return [self._vector_to_chunk[v] for v in vids if v in self._vector_to_chunk]

    def get_stats(self) -> IndexStatsResponse:
        with self._lock:
            model_info = embedding_service.get_model_info()
            total_chunks = len(self._vector_to_chunk)
            total_vectors = self._index.ntotal
            total_docs = len(self._documents)

            return IndexStatsResponse(
                total_documents=total_docs,
                total_chunks=total_chunks,
                total_vectors=total_vectors,
                dimension=self.dimension,
                embedding_model=model_info["model_name"],
                model_license=model_info["license"],
                index_type="FAISS IndexFlatIP (Cosine Similarity via L2 Normalized Embeddings)",
                memory_usage_mb=model_info["memory_usage_approx_mb"],
                status="ready" if model_info["is_loaded"] else "standby"
            )

    def clear_all(self):
        """Reset index and metadata completely."""
        with self._lock:
            self._index = faiss.IndexFlatIP(self.dimension)
            self._vector_to_chunk.clear()
            self._documents.clear()
            self._doc_to_vector_ids.clear()
            self._filename_to_doc_id.clear()
            self._next_vector_id = 0
            if self.index_file and os.path.exists(self.index_file):
                os.remove(self.index_file)
            if self.metadata_file and os.path.exists(self.metadata_file):
                os.remove(self.metadata_file)
            try:
                self.bm25.clear_all()
            except Exception:
                pass

vector_store = VectorStore(dimension=384)
