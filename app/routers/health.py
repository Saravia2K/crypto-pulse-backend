"""
Health-check and rate-limit status endpoints.
Neither endpoint applies rate limiting so they are safe for external monitors.
"""
import logging
import time

from fastapi import APIRouter, Request, Response

from app.core.cache import cache
from app.core.config import settings
from app.schemas.crypto import HealthDependency, HealthResponse, RateLimitStatusResponse
from app.services.coincap import coincap_service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["ops"])


@router.get("/health", response_model=HealthResponse, summary="Service health check")
async def health_check(request: Request, response: Response) -> HealthResponse:
    """
    Verify the health of the API and its dependencies (Redis, CoinCap).
    No rate limiting is applied so monitoring tools can poll freely.
    """
    # Check Redis / in-memory cache
    redis_ok = await cache.ping()
    redis_dep = HealthDependency(
        status="ok" if redis_ok else "degraded",
        detail=f"backend={cache.backend_name}",
    )

    # Check CoinCap API reachability
    coincap_ok = await coincap_service.ping()
    coincap_dep = HealthDependency(
        status="ok" if coincap_ok else "degraded",
        detail=None if coincap_ok else "CoinCap API unreachable",
    )

    overall = "ok" if (redis_ok and coincap_ok) else "degraded"
    return HealthResponse(
        status=overall,
        redis=redis_dep,
        coincap_api=coincap_dep,
        timestamp=int(time.time()),
    )


@router.get(
    "/rate-limit/status",
    response_model=RateLimitStatusResponse,
    summary="Current rate-limit status for this client",
)
async def rate_limit_status(request: Request) -> RateLimitStatusResponse:
    """
    Return the configured rate-limit parameters along with the current
    remaining allowance for this client's IP (best-effort from request state).
    """
    view_rate_limit = getattr(request.state, "view_rate_limit", None)
    remaining: int | None = None
    reset_at: int | None = None

    if view_rate_limit:
        _, remaining, reset_time = view_rate_limit
        reset_at = int(reset_time)
        remaining = max(remaining, 0)

    return RateLimitStatusResponse(
        limit=settings.rate_limit_requests,
        period_seconds=settings.rate_limit_period,
        requests_remaining=remaining,
        reset_at=reset_at,
    )
