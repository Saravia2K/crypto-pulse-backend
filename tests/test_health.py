"""Tests for /health and /rate-limit/status endpoints."""
import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_health_ok(client):
    """Health endpoint returns 200 with expected keys."""
    with (
        patch("app.routers.health.cache") as mock_cache,
        patch("app.routers.health.coincap_service") as mock_coincap,
    ):
        mock_cache.ping = AsyncMock(return_value=True)
        mock_cache.backend_name = "memory"
        mock_coincap.ping = AsyncMock(return_value=True)

        resp = await client.get("/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "redis" in body
    assert "coincap_api" in body
    assert "timestamp" in body


@pytest.mark.asyncio
async def test_health_degraded_when_coincap_down(client):
    """Health endpoint reports degraded when CoinCap is unreachable."""
    with (
        patch("app.routers.health.cache") as mock_cache,
        patch("app.routers.health.coincap_service") as mock_coincap,
    ):
        mock_cache.ping = AsyncMock(return_value=True)
        mock_cache.backend_name = "memory"
        mock_coincap.ping = AsyncMock(return_value=False)

        resp = await client.get("/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["coincap_api"]["status"] == "degraded"


@pytest.mark.asyncio
async def test_rate_limit_status(client):
    """Rate-limit status endpoint returns the configured defaults."""
    resp = await client.get("/rate-limit/status")
    assert resp.status_code == 200
    body = resp.json()
    assert "limit" in body
    assert "period_seconds" in body
