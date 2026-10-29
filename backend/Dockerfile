# ==============================================================================
# AI Document Intelligence System - Backend Dockerfile
# Optimized for CPU inference (₹0-cost, minimal image size, zero GPU dependencies)
# ==============================================================================

FROM python:3.11-slim

# Prevent Python from writing .pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000
ENV HOST=0.0.0.0
ENV ENVIRONMENT=production

WORKDIR /app

# Install system dependencies (build-essential needed for some C extensions if wheel unavailable)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file first for layer caching
COPY requirements.txt .

# Install CPU-optimized PyTorch to minimize image footprint (~150MB vs ~2GB with CUDA)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY app/ ./app/

# Pre-create data persistence and model cache directories
ENV DATA_DIR=/app/data
ENV HF_HOME=/app/model_cache
RUN mkdir -p /app/data /app/model_cache

# Pre-cache sentence transformer weights during image build for reproducible offline runtime
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2', device='cpu')"

# Volume mount for persistent FAISS index and BM25 metadata across restarts
VOLUME ["/app/data"]

EXPOSE 8000

# Health check to ensure FastAPI container is serving traffic
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
