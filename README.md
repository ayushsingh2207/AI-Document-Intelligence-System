# AI Document Intelligence System

An advanced, production-grade NLP & Document Processing System built with **Next.js 16**, **TypeScript**, **Tailwind CSS**, and a **Python FastAPI** backend.

> **Target Budget:** ₹0-cost architecture. Zero paid APIs, no fake AI responses, no hardcoded secrets, strict type safety, and 100% deterministic local text extraction.

---

## Phase 1 Overview: Ingestion, Validation & Text Extraction Engine

Phase 1 establishes the rock-solid foundation for document intelligence:
- **Multi-Format Ingestion:** Accepts `.pdf`, `.docx`, and `.txt` files up to 15 MB.
- **Deep Validation & Security:**
  - MIME-type and magic-byte signature inspection (`%PDF-` for PDFs, OpenXML ZIP structure for DOCX, null-byte checks for TXT).
  - Path traversal defense & filename sanitization.
  - Chunked file reading to prevent memory exhaustion / DoS attacks.
- **Page-Preserved Extraction:**
  - **PDF:** 1-indexed page extraction preserving layout boundaries via `pypdf`.
  - **DOCX:** XML page break detection (`w:type="page"` and `w:lastRenderedPageBreak`) and structured paragraph chunking via `python-docx`.
  - **TXT:** Form-feed (`\x0c`) pagination and logical token batching.
- **Interactive Dashboard:**
  - Real-time backend health check indicator with live latency and version.
  - Drag-and-drop upload zone with client-side pre-validation and built-in 1-click demo documents.
  - Page-by-page reader, continuous document stream, and structured API JSON inspector.
  - Live in-page text search and word/character count metrics.

---

## Project Structure

```
ai-document-intelligence/
├── .git/
├── .gitignore
├── .env.example
├── README.md
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py            # FastAPI entry point, CORS & security middleware
│   │   ├── config.py          # App settings & environment loader
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── health.py      # GET /health
│   │   │   └── documents.py   # POST /api/documents/upload & /validate
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── validator.py   # Magic-byte check, size limiter & sanitization
│   │   │   └── extractor.py   # Pure Python PDF/DOCX/TXT extraction
│   │   └── schemas/
│   │       ├── __init__.py
│   │       └── document.py    # Pydantic v2 data models
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py        # TestClient fixture
│   │   └── test_documents.py  # 12 unit/integration test cases
│   ├── pytest.ini
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── src/
    │   ├── app/
    │   │   ├── layout.tsx     # Root layout with font optimization & dark theme
    │   │   ├── page.tsx       # Main document intelligence dashboard
    │   │   └── globals.css    # Tailwind CSS v4 styling & animations
    │   ├── components/
    │   │   ├── Navbar.tsx     # Navigation bar with live backend status
    │   │   ├── MetricsCards.tsx # Session statistics (docs, pages, words)
    │   │   ├── FileUpload.tsx # Drag-and-drop zone with pre-validation & demo presets
    │   │   └── DocumentViewer.tsx # Page-preserved reader, search & JSON exporter
    │   └── lib/
    │       └── api.ts         # TypeScript API client
    ├── package.json
    ├── tsconfig.json
    └── .env.example
```

---

## Prerequisites

- **Node.js:** v18+ (tested on v24)
- **Python:** 3.10+ (tested on 3.14)
- **Git**

---

## Quickstart: Running Locally

### 1. Backend Setup (FastAPI)

```bash
# Navigate to the backend directory
cd backend

# Create and activate virtual environment
python -m venv venv

# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Linux / macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment variables
cp .env.example .env

# Run FastAPI backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

The backend will be live at:
- **API Root:** [http://localhost:8000](http://localhost:8000)
- **Interactive Swagger Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check:** [http://localhost:8000/health](http://localhost:8000/health)

### 2. Frontend Setup (Next.js)

```bash
# Open a new terminal and navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Copy environment variables
cp .env.example .env.local

# Run Next.js development server
npm run dev
```

The frontend will be live at [http://localhost:3000](http://localhost:3000).

---

## Running Automated Tests

Run backend integration and unit tests:

```bash
cd backend
.\venv\Scripts\Activate.ps1  # Windows
pytest -v
```

**Test Coverage Summary:**
- Health check and environment verification
- API root and supported MIME types
- Rejection of 0-byte empty files (400 Bad Request)
- Rejection of unsupported extensions (400 Bad Request)
- Rejection of corrupt PDF & DOCX magic bytes (400 Bad Request)
- TXT upload with form-feed page demarcation
- DOCX upload with dynamic page break detection and XML parsing
- PDF upload with multi-page reader verification
- Path traversal sanitization security checks
- Fast validation endpoint (`/api/documents/validate`)

---

## Free Cloud Deployment Guide (₹0 Cost)

### Frontend Deployment on Vercel
1. Push your repository to GitHub.
2. Sign in to [Vercel](https://vercel.com) and import the repository.
3. Configure project settings:
   - **Root Directory:** `frontend`
   - **Framework Preset:** `Next.js`
4. In **Environment Variables**, set:
   - `NEXT_PUBLIC_API_URL`: URL of your deployed Python backend (e.g. `https://your-api.onrender.com`).
5. Click **Deploy**.

### Backend Deployment on Free Python Host (e.g. Render / Railway / Hugging Face Spaces)
1. In Render, select **New Web Service** and connect your GitHub repository.
2. Set settings:
   - **Root Directory:** `backend`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
3. In **Environment Variables**, configure:
   - `ALLOWED_ORIGINS`: `https://your-frontend-app.vercel.app`
   - `MAX_UPLOAD_SIZE_MB`: `15`
   - `ENVIRONMENT`: `production`
4. Click **Create Web Service**.

---

## Phase 2 Roadmap: Semantic Chunking & Vector Retrieval

Before transitioning to Phase 2, ensure Phase 1 ingestion outputs meet your document schema expectations:
1. **Semantic Chunking:** Implement sentence-window and paragraph-aware chunkers with sliding token overlap.
2. **Local Embedding Engine (₹0-Cost):** Integrate FastEmbed or sentence-transformers (`all-MiniLM-L6-v2`) running completely locally without external API costs.
3. **Local Vector Store:** Connect ChromaDB or embedded Qdrant for semantic indexing across extracted pages.
4. **Hybrid Search:** Enable keyword (BM25) and semantic vector search mapped back to exact page numbers.
