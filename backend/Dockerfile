# ==============================================================================
# AI Document Intelligence System - Backend Dockerfile
# Optimized for Hugging Face Spaces (CPU Basic: 2 vCPU, 16 GB RAM, ₹0 budget)
# UID 1000 non-root user, port 7860, pre-cached embedding weights
# ==============================================================================

FROM python:3.11-slim

# Prevent Python from writing .pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=7860
ENV HOST=0.0.0.0
ENV ENVIRONMENT=production
ENV DEMO_MODE=true

# Create a non-root user with UID 1000 (required by Hugging Face Spaces)
RUN useradd -m -u 1000 user

WORKDIR /app

# Install system dependencies (curl required for health checks)
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

# Pre-create data persistence, demo storage, and model cache directories
ENV DATA_DIR=/app/data
ENV DEMO_DATA_DIR=/app/data/demo
ENV HF_HOME=/app/model_cache

RUN mkdir -p /app/data/demo /app/model_cache

# Pre-cache sentence transformer weights during image build for reproducible offline runtime
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2', device='cpu')"

# Assign ownership of /app to the non-root user
RUN chown -R user:user /app

# Switch to non-root user
USER user
ENV HOME=/home/user

EXPOSE 7860

# Health check to ensure FastAPI container is serving traffic
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:7860/health || exit 1

CMD ["sh", "-c", "exec python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
