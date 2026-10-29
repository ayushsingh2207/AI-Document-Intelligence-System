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

    # Public Demo Mode
    # Default to False for local development; set to True in public portfolio deployments
    DEMO_MODE: bool = os.getenv("DEMO_MODE", "false").lower() in ("true", "1", "yes")

    # Storage Paths (Isolated demo store prevents exposing private local documents)
    DATA_DIR: str = os.getenv(
        "DATA_DIR",
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    )
    DEMO_DATA_DIR: str = os.getenv(
        "DEMO_DATA_DIR",
        os.path.join(DATA_DIR, "demo")
    )

    @property
    def active_data_dir(self) -> str:
        """Return the active storage directory (isolated demo store in demo mode)."""
        if self.DEMO_MODE:
            return self.DEMO_DATA_DIR
        return self.DATA_DIR

    # Rate Limiting Configuration
    RATE_LIMIT_ENABLED: bool = os.getenv("RATE_LIMIT_ENABLED", "true").lower() in ("true", "1", "yes")
    RATE_LIMIT_DEFAULT: str = os.getenv("RATE_LIMIT_DEFAULT", "60/minute")
    RATE_LIMIT_UPLOAD: str = os.getenv("RATE_LIMIT_UPLOAD", "5/minute")
    RATE_LIMIT_SEARCH: str = os.getenv("RATE_LIMIT_SEARCH", "20/minute")
    RATE_LIMIT_QA: str = os.getenv("RATE_LIMIT_QA", "15/minute")
    RATE_LIMIT_CONTRACT: str = os.getenv("RATE_LIMIT_CONTRACT", "10/minute")

    # CORS origins
    @property
    def cors_origins(self) -> List[str]:
        raw = os.getenv("ALLOWED_ORIGINS")
        if raw is None:
            # In production, never silently fall back to localhost
            if self.ENVIRONMENT == "production":
                return []
            return ["http://localhost:3000", "http://127.0.0.1:3000"]
        origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
        # Disallow wildcard in production
        if self.ENVIRONMENT == "production" and "*" in origins:
            return [o for o in origins if o != "*"]
        return origins

    def validate_production_configuration(self) -> None:
        """
        Validate required settings when running in production.
        Prevents silent fallbacks and insecure configurations.
        """
        if self.ENVIRONMENT == "production":
            if not self.cors_origins:
                raise ValueError(
                    "Production configuration error: ALLOWED_ORIGINS must be set to at least "
                    "one trusted public domain when ENVIRONMENT=production. Silent localhost fallback is forbidden."
                )


settings = Settings()

