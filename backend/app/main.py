import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.services.limiter import limiter
from app.services.vector_store import vector_store
from app.services.demo_corpus import ensure_demo_corpus_indexed
from app.routers import health_router, documents_router, search_router, qa_router, contract_router

docs_url = "/docs" if settings.ENABLE_DOCS else None
redoc_url = "/redoc" if settings.ENABLE_DOCS else None
openapi_url = "/openapi.json" if settings.ENABLE_DOCS else None

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Phase 6.4: Grounded Q&A, CUAD Contract Intelligence, and Hardened Public Demo Mode",
    docs_url=docs_url,
    redoc_url=redoc_url,
    openapi_url=openapi_url,
)

# Attach SlowAPI Rate Limiter
app.state.limiter = limiter

# Startup event: configuration validation & demo corpus indexing
@app.on_event("startup")
async def startup_event():
    if settings.ENVIRONMENT == "production":
        settings.validate_production_configuration()
    if settings.DEMO_MODE:
        ensure_demo_corpus_indexed(vector_store)

# CORS configuration
is_wildcard = settings.cors_origins == ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=not is_wildcard,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request timing & security middleware
@app.middleware("http")
async def add_process_time_and_security_headers(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = f"{process_time:.4f}s"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response

# Rate limit exceeded handler
@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={
            "success": False,
            "error": "Rate limit exceeded",
            "detail": f"Rate limit exceeded: {exc.detail}. Please slow down your requests."
        },
        headers={"Retry-After": "60"}
    )

# Validation error handling
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "error": "Request validation error",
            "details": exc.errors()
        }
    )

# Global unhandled exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    detail = str(exc) if settings.ENVIRONMENT == "development" else "An unexpected internal server error occurred."
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error",
            "detail": detail
        }
    )

# Include Routers
app.include_router(health_router)
app.include_router(search_router)
app.include_router(qa_router)
app.include_router(contract_router)
app.include_router(documents_router)

@app.get("/", tags=["Root"])
async def root():
    return {
        "message": "Welcome to AI Document Intelligence System API",
        "version": settings.VERSION,
        "phase": "Phase 6.4 - Grounded Q&A, CUAD Intelligence, and Hardened Public Demo Mode",
        "demo_mode": settings.DEMO_MODE,
        "rate_limiting_enabled": settings.RATE_LIMIT_ENABLED,
        "embedding_model": "sentence-transformers/all-MiniLM-L6-v2 (384-d)",
        "vector_index": "FAISS IndexFlatIP (Cosine Similarity)",
        "lexical_index": "BM25Okapi (rank_bm25)",
        "fusion_method": "Reciprocal Rank Fusion (RRF)",
        "qa_engine": "Extractive Evidence-Grounding with Conservative Abstention",
        "docs_url": "/docs" if settings.ENABLE_DOCS else None,
        "health_url": "/health"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
