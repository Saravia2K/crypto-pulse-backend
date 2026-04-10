"""
Cryptocurrency endpoints.

Route order matters: /search must be declared before /{id} so that FastAPI
does not treat the literal string "search" as an asset identifier.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Path, Query, Request, Response

from app.core.cache import cache
from app.core.config import settings
from app.core.exceptions import CryptocurrencyNotFound
from app.core.rate_limiter import limiter
from app.schemas.crypto import (
    CryptoDetailResponse,
    HistoryResponse,
    SearchResponse,
    TopCryptosResponse,
)
from app.services.coincap import coincap_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/crypto", tags=["crypto"])


# ---------------------------------------------------------------------------
# GET /api/crypto/search  (must be before /{id})
# ---------------------------------------------------------------------------

@router.get("/search", response_model=SearchResponse, summary="Search cryptocurrencies")
@limiter.limit("50/minute")
async def search_cryptos(
    request: Request,
    response: Response,
    q: str = Query("", description="Search term (name or symbol)"),
) -> SearchResponse:
    """
    Search cryptocurrencies by name or symbol via CoinPaprika.
    Returns an empty list when *q* is shorter than 2 characters (no error).
    Cached for 2 minutes.
    """
    if len(q.strip()) < 2:
        return SearchResponse(data=[], query=q, count=0)

    cache_key = f"search:{q.strip().lower()}"
    cached = await cache.get(cache_key)
    if cached:
        return SearchResponse(**cached)

    raw = await coincap_service.search_assets(q.strip())
    assets = raw.get("data") or []

    # Secondary filter so partial matches on name/symbol are always included
    q_lower = q.strip().lower()
    assets = [
        a for a in assets
        if q_lower in a.get("name", "").lower()
        or q_lower in a.get("symbol", "").lower()
        or q_lower in a.get("id", "").lower()
    ]

    result = SearchResponse(data=assets, query=q, count=len(assets))
    await cache.set(cache_key, result.model_dump(), settings.cache_ttl_search)
    return result


# ---------------------------------------------------------------------------
# GET /api/crypto/top/{limit}
# ---------------------------------------------------------------------------

@router.get(
    "/top/{limit}",
    response_model=TopCryptosResponse,
    summary="Top N cryptocurrencies by market cap",
)
@limiter.limit("100/minute")
async def get_top_cryptos(
    request: Request,
    response: Response,
    limit: int = Path(..., ge=1, le=100, description="Number of results (1-100)"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
) -> TopCryptosResponse:
    """
    Return the top *limit* cryptocurrencies ordered by market cap (descending).
    Cached for 5 minutes.
    """
    cache_key = f"top:{limit}:{offset}"
    cached = await cache.get(cache_key)
    if cached:
        return TopCryptosResponse(**cached)

    raw = await coincap_service.get_assets(limit=limit, offset=offset)
    result = TopCryptosResponse(
        data=raw.get("data", []),
        timestamp=raw.get("timestamp", 0),
        limit=limit,
        offset=offset,
    )
    await cache.set(cache_key, result.model_dump(), settings.cache_ttl_top)
    return result


# ---------------------------------------------------------------------------
# GET /api/crypto/{id}/history
# ---------------------------------------------------------------------------

@router.get(
    "/{crypto_id}/history",
    response_model=HistoryResponse,
    summary="Historical prices for a cryptocurrency",
)
@limiter.limit("100/minute")
async def get_crypto_history(
    request: Request,
    response: Response,
    crypto_id: str = Path(..., description="Asset identifier, e.g. btc"),
    days: int = Query(7, ge=1, le=30, description="Number of days (1-30, default 7)"),
) -> HistoryResponse:
    """
    Return daily price history for *crypto_id* over the last *days* days.
    Raises 404 if the asset does not exist. Cached for 5 minutes.
    """
    cache_key = f"history:{crypto_id}:{days}"
    cached = await cache.get(cache_key)
    if cached:
        return HistoryResponse(**cached)

    raw = await coincap_service.get_asset_history(crypto_id, days=days)
    if not raw.get("data"):
        # Verify the asset exists (raises CryptocurrencyNotFound if not)
        await coincap_service.get_asset(crypto_id)

    result = HistoryResponse(
        data=raw.get("data", []),
        id=crypto_id,
        days=days,
    )
    await cache.set(cache_key, result.model_dump(), settings.cache_ttl_history)
    return result


# ---------------------------------------------------------------------------
# GET /api/crypto/{id}
# ---------------------------------------------------------------------------

@router.get(
    "/{crypto_id}",
    response_model=CryptoDetailResponse,
    summary="Cryptocurrency detail",
)
@limiter.limit("200/minute")
async def get_crypto_detail(
    request: Request,
    response: Response,
    crypto_id: str = Path(..., description="Asset identifier, e.g. btc"),
) -> CryptoDetailResponse:
    """
    Return full detail for a single cryptocurrency.
    Raises 404 if the asset does not exist. Cached for 1 minute.
    """
    cache_key = f"detail:{crypto_id}"
    cached = await cache.get(cache_key)
    if cached:
        return CryptoDetailResponse(**cached)

    raw = await coincap_service.get_asset(crypto_id)
    result = CryptoDetailResponse(
        data=raw["data"],
        timestamp=raw.get("timestamp", 0),
    )
    await cache.set(cache_key, result.model_dump(), settings.cache_ttl_detail)
    return result
