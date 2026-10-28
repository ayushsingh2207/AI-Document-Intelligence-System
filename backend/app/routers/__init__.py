from .health import router as health_router
from .documents import router as documents_router
from .search import router as search_router

__all__ = ["health_router", "documents_router", "search_router"]
