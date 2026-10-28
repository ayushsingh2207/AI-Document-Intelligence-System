import threading
import logging
from typing import List, Dict, Any, Optional
import numpy as np

logger = logging.getLogger(__name__)

class EmbeddingService:
    """
    Thread-safe Singleton service for local embedding generation.
    Uses sentence-transformers/all-MiniLM-L6-v2 (Apache 2.0 License).
    Generates 384-dimensional unit-normalized embeddings for cosine similarity.
    """
    _instance: Optional["EmbeddingService"] = None
    _lock = threading.Lock()

    MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
    DIMENSION = 384
    LICENSE = "Apache-2.0"

    def __init__(self):
        self._model = None
        self._load_lock = threading.Lock()
        self._is_loaded = False

    @classmethod
    def get_instance(cls) -> "EmbeddingService":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def load_model(self):
        """Lazy loader ensuring model is loaded once and cached in memory."""
        if self._is_loaded and self._model is not None:
            return self._model

        with self._load_lock:
            if not self._is_loaded or self._model is None:
                try:
                    logger.info("Loading embedding model '%s' on CPU...", self.MODEL_NAME)
                    from sentence_transformers import SentenceTransformer
                    self._model = SentenceTransformer(self.MODEL_NAME, device="cpu")
                    self._is_loaded = True
                    logger.info("Successfully loaded '%s' (dim=%d)", self.MODEL_NAME, self.DIMENSION)
                except Exception as exc:
                    logger.error("Failed to load embedding model '%s': %s", self.MODEL_NAME, str(exc))
                    raise RuntimeError(
                        f"Could not load embedding model '{self.MODEL_NAME}': {str(exc)}"
                    ) from exc
        return self._model

    def embed_texts(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        """
        Embed a list of text strings into normalized 384-dim float32 embeddings.
        Returns: np.ndarray of shape (len(texts), 384)
        """
        if not texts:
            return np.empty((0, self.DIMENSION), dtype=np.float32)

        model = self.load_model()
        try:
            # normalize_embeddings=True makes inner product identical to cosine similarity
            embeddings = model.encode(
                texts,
                batch_size=batch_size,
                show_progress_bar=False,
                normalize_embeddings=True,
                convert_to_numpy=True
            )
            return embeddings.astype(np.float32)
        except Exception as exc:
            logger.error("Error during batch embedding generation: %s", str(exc))
            raise RuntimeError(f"Embedding generation failed: {str(exc)}") from exc

    def embed_query(self, query: str) -> np.ndarray:
        """
        Embed a single query into a normalized 384-dim float32 vector.
        Returns: np.ndarray of shape (1, 384)
        """
        if not query or not query.strip():
            raise ValueError("Query string cannot be empty")

        embeddings = self.embed_texts([query.strip()])
        return embeddings

    def get_model_info(self) -> Dict[str, Any]:
        return {
            "model_name": self.MODEL_NAME,
            "dimension": self.DIMENSION,
            "license": self.LICENSE,
            "device": "cpu",
            "is_loaded": self._is_loaded,
            "description": "384-dimensional dense semantic representations optimized for similarity search (Apache 2.0)",
            "memory_usage_approx_mb": 120.0,
        }

embedding_service = EmbeddingService.get_instance()
