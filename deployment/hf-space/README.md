---
title: AI Document Intelligence API
emoji: 📄
colorFrom: indigo
colorTo: cyan
sdk: docker
app_port: 7860
suggested_hardware: cpu-basic
pinned: false
---

# AI Document Intelligence System — Backend API

Production Docker Space hosting the FastAPI backend for the **AI Document Intelligence System**.

- **Hardware**: CPU Basic (2 vCPU, 16 GB RAM, ₹0 budget)
- **Container Port**: `7860` (listening on `0.0.0.0:7860`)
- **Runtime User**: Non-root user with UID `1000` (`user`)
- **Mode**: Public Demo Mode (`DEMO_MODE=true`)
- **Inference**: Local CPU-optimized PyTorch with pre-cached `sentence-transformers/all-MiniLM-L6-v2`
- **Retrieval Engine**: FAISS IndexFlatIP (Dense) + BM25Okapi (Lexical) fused with Reciprocal Rank Fusion (RRF)
- **Frontend App**: Deployed on Vercel at your configured frontend domain

---

## Required Space Secrets & Environment Variables

Configure these in your Hugging Face Space **Settings -> Variables and secrets**:

| Variable | Recommended Value | Description |
| :--- | :--- | :--- |
| `ENVIRONMENT` | `production` | Enables production security checks and disables Swagger UI |
| `DEMO_MODE` | `true` | Enforces read-only demo safety (disables document upload and deletion) |
| `ALLOWED_ORIGINS` | `https://<your-vercel-domain>.vercel.app` | Whitelists your production frontend domain for CORS |
| `PORT` | `7860` | Default listening port (required by Spaces) |
| `HOST` | `0.0.0.0` | Network binding interface |
| `RATE_LIMIT_ENABLED` | `true` | Protects CPU endpoints against request bursts |

---

## Deployment Architecture

In a monorepo setup, Hugging Face Spaces requires a `Dockerfile` and `README.md` at the root of the Space repository.

To deploy this backend API to your Space:
1. Create a new Space on Hugging Face:
   - **Name**: `ai-document-intelligence-api`
   - **SDK**: **Docker** (Blank)
   - **Hardware**: **CPU Basic** (Free)
2. Add your Hugging Face Space as a remote or push the `backend` contents to the Space Git repository:
   ```bash
   # Clone the empty Space
   git clone https://huggingface.co/spaces/<your-username>/ai-document-intelligence-api hf-space-repo

   # Copy backend files and this README to the Space repo root
   cp -r backend/* hf-space-repo/
   cp deployment/hf-space/README.md hf-space-repo/README.md

   # Commit and push to Hugging Face
   cd hf-space-repo
   git add .
   git commit -m "deploy: backend Docker container on Hugging Face Spaces"
   git push origin main
   ```
3. Once the build completes, the backend API is live at:
   `https://<your-username>-ai-document-intelligence-api.hf.space`

---

## Live Endpoints

- `GET /health`: Health status probe, environment, and limits.
- `GET /api/documents`: List pre-indexed educational sample documents.
- `POST /api/documents/search`: Hybrid passage search (Dense + BM25 + RRF).
- `POST /api/documents/qa`: Evidence-grounded Q&A with verifiable citations and abstention.
- `GET /api/documents/contract/categories`: 41 CUAD legal contract categories.
- `POST /api/documents/{doc_id}/contract-analysis`: Academic clause trigger extraction.
