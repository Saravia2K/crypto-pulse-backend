"""
Rate-limiter configuration using slowapi (a Starlette/FastAPI wrapper around
the `limits` library).  Redis is used as the storage backend when available so
that limits are shared across multiple API workers/instances.
"""
import logging

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

logger = logging.getLogger(__name__)


def _build_limiter() -> Limiter:
    try:
        lim = Limiter(
            key_func=get_remote_address,
            storage_uri=settings.redis_url,
            default_limits=[f"{settings.rate_limit_requests}/minute"],
        )
        logger.info("Rate limiter: using Redis storage at %s", settings.redis_url)
        return lim
    except Exception as exc:
        logger.warning("Rate limiter: falling back to in-memory storage (%s)", exc)
        return Limiter(
            key_func=get_remote_address,
            default_limits=[f"{settings.rate_limit_requests}/minute"],
        )


limiter = _build_limiter()
