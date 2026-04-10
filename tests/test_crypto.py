"""Tests for /api/crypto/* endpoints."""
import pytest
from unittest.mock import AsyncMock, patch

FAKE_ASSET = {
    "id": "bitcoin",
    "rank": "1",
    "symbol": "BTC",
    "name": "Bitcoin",
    "supply": "19000000",
    "max_supply": "21000000",
    "market_cap_usd": "500000000000",
    "volume_usd_24hr": "20000000000",
    "price_usd": "26000.00",
    "change_percent_24hr": "1.5",
    "vwap_24hr": "25900.00",
    "explorer": "https://blockchain.info/",
}

FAKE_HISTORY_POINT = {
    "price_usd": "26000.00",
    "time": 1680000000000,
    "date": "2023-03-28T00:00:00.000Z",
}


# ---------------------------------------------------------------------------
# GET /api/crypto/top/{limit}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_top_cryptos(client):
    """Returns a list of assets with correct schema."""
    raw_response = {
        "data": [FAKE_ASSET],
        "timestamp": 1680000000000,
    }
    with patch(
        "app.routers.crypto.coincap_service.get_assets",
        new_callable=AsyncMock,
        return_value=raw_response,
    ):
        resp = await client.get("/api/crypto/top/1")

    assert resp.status_code == 200
    body = resp.json()
    assert body["limit"] == 1
    assert len(body["data"]) == 1
    assert body["data"][0]["id"] == "bitcoin"


@pytest.mark.asyncio
async def test_get_top_cryptos_limit_validation(client):
    """Limit must be between 1 and 100."""
    resp = await client.get("/api/crypto/top/0")
    assert resp.status_code == 422

    resp = await client.get("/api/crypto/top/101")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_top_cryptos_uses_cache(client):
    """Second call should hit the cache, not the service."""
    raw_response = {"data": [FAKE_ASSET], "timestamp": 1680000000000}
    with patch(
        "app.routers.crypto.coincap_service.get_assets",
        new_callable=AsyncMock,
        return_value=raw_response,
    ) as mock_get:
        await client.get("/api/crypto/top/1")
        await client.get("/api/crypto/top/1")
        assert mock_get.call_count == 1  # second call served from cache


# ---------------------------------------------------------------------------
# GET /api/crypto/{id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_crypto_detail(client):
    """Returns asset detail with correct schema."""
    raw_response = {"data": FAKE_ASSET, "timestamp": 1680000000000}
    with patch(
        "app.routers.crypto.coincap_service.get_asset",
        new_callable=AsyncMock,
        return_value=raw_response,
    ):
        resp = await client.get("/api/crypto/bitcoin")

    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["id"] == "bitcoin"


@pytest.mark.asyncio
async def test_get_crypto_detail_not_found(client):
    """Returns 404 when the asset does not exist."""
    from app.core.exceptions import CryptocurrencyNotFound

    with patch(
        "app.routers.crypto.coincap_service.get_asset",
        new_callable=AsyncMock,
        side_effect=CryptocurrencyNotFound("nonexistent-coin"),
    ):
        resp = await client.get("/api/crypto/nonexistent-coin")

    assert resp.status_code == 404
    body = resp.json()
    assert body["error"] == "not_found"
    assert body["id"] == "nonexistent-coin"


# ---------------------------------------------------------------------------
# GET /api/crypto/{id}/history
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_crypto_history(client):
    """Returns history points with correct schema."""
    raw_response = {"data": [FAKE_HISTORY_POINT], "timestamp": 1680000000000}
    with patch(
        "app.routers.crypto.coincap_service.get_asset_history",
        new_callable=AsyncMock,
        return_value=raw_response,
    ):
        resp = await client.get("/api/crypto/bitcoin/history?days=7")

    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "bitcoin"
    assert body["days"] == 7
    assert len(body["data"]) == 1


@pytest.mark.asyncio
async def test_get_crypto_history_days_validation(client):
    """days must be between 1 and 30."""
    resp = await client.get("/api/crypto/bitcoin/history?days=0")
    assert resp.status_code == 422

    resp = await client.get("/api/crypto/bitcoin/history?days=31")
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/crypto/search
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_cryptos(client):
    """Returns matching assets."""
    raw_response = {"data": [FAKE_ASSET], "timestamp": 1680000000000}
    with patch(
        "app.routers.crypto.coincap_service.search_assets",
        new_callable=AsyncMock,
        return_value=raw_response,
    ):
        resp = await client.get("/api/crypto/search?q=bitcoin")

    assert resp.status_code == 200
    body = resp.json()
    assert body["query"] == "bitcoin"
    assert body["count"] >= 1


@pytest.mark.asyncio
async def test_search_too_short_returns_empty(client):
    """Query shorter than 2 chars returns empty list, not an error."""
    resp = await client.get("/api/crypto/search?q=b")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"] == []
    assert body["count"] == 0


@pytest.mark.asyncio
async def test_search_empty_query_returns_empty(client):
    """Empty query returns empty list."""
    resp = await client.get("/api/crypto/search?q=")
    assert resp.status_code == 200
    assert resp.json()["data"] == []
