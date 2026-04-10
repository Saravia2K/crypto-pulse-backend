"""
Shared pytest fixtures for CryptoPulse test suite.
"""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.cache import cache
from app.main import app


@pytest_asyncio.fixture(autouse=True)
async def _reset_cache():
    """Ensure the in-memory cache starts fresh for every test."""
    await cache.connect()
    cache._use_redis = False  # Force in-memory so tests are self-contained
    cache._fallback._store.clear()
    yield
    cache._fallback._store.clear()


@pytest_asyncio.fixture
async def client():
    """Async HTTPX test client wired to the FastAPI app."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
