from slowapi import Limiter
from slowapi.util import get_remote_address
from app.config import settings

# Thread-safe rate limiter using client IP address
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[settings.RATE_LIMIT_DEFAULT] if settings.RATE_LIMIT_DEFAULT else [],
    enabled=settings.RATE_LIMIT_ENABLED,
)
