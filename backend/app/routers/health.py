from fastapi import APIRouter
from app.config import settings
from app.schemas.document import HealthResponse

router = APIRouter(tags=["Health & Status"])

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint verifying system availability, configuration and limits.
    """
    return HealthResponse(
        status="healthy",
        service=settings.PROJECT_NAME,
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
        max_upload_size_mb=settings.MAX_UPLOAD_SIZE_MB,
        supported_formats=sorted(list(settings.ALLOWED_EXTENSIONS)),
        demo_mode=settings.DEMO_MODE,
        rate_limit_enabled=settings.RATE_LIMIT_ENABLED,
    )
