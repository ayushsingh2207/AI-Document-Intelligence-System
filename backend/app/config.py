import os
from typing import List
from dotenv import load_dotenv

# Load .env if present
load_dotenv()

class Settings:
    PROJECT_NAME: str = "AI Document Intelligence System"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

    # Security & File Limits
    # 15 MB default limit
    MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "15"))
    MAX_UPLOAD_SIZE_BYTES: int = MAX_UPLOAD_SIZE_MB * 1024 * 1024

    ALLOWED_EXTENSIONS: set = {".pdf", ".docx", ".txt"}
    
    ALLOWED_MIME_TYPES: set = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
        "application/octet-stream"
    }

    # Documentation & Developer UI controls
    # Default to enabling Swagger/ReDoc in development, but disable in production unless explicitly opted in
    ENABLE_DOCS: bool = os.getenv(
        "ENABLE_DOCS",
        "true" if os.getenv("ENVIRONMENT", "development").lower() == "development" else "false"
    ).lower() in ("true", "1", "yes")

    # CORS origins
    @property
    def cors_origins(self) -> List[str]:
        raw = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
        if not raw:
            # If empty in development, allow local dev origin; never wildcard in production
            return ["http://localhost:3000", "http://127.0.0.1:3000"] if self.ENVIRONMENT == "development" else []
        origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
        # Disallow wildcard in production
        if self.ENVIRONMENT == "production" and "*" in origins:
            return [o for o in origins if o != "*"]
        return origins

settings = Settings()

