import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.limiter import limiter

@pytest.fixture(autouse=True)
def configure_test_limiter():
    """Disable rate limiting during automated test suite execution so benchmark loops aren't throttled."""
    orig = limiter.enabled
    limiter.enabled = False
    limiter.reset()
    yield
    limiter.enabled = orig

@pytest.fixture
def client():
    """FastAPI TestClient fixture."""
    return TestClient(app)
