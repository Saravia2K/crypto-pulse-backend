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
    # No default_limits: every endpoint that needs rate limiting declares its
    # own @limiter.limit() decorator. Endpoints without a decorator (e.g.
    # /health, /rate-limit/status) are intentionally exempt — applying
    # default_limits would cause 500 errors on those routes when Redis is
    # unavailable because the storage check fires even for undecorated routes.
    try:
        client = Limiter(
            key_func=get_remote_address,
            storage_uri=settings.redis_url,
        )
        logger.info("Rate limiter: using Redis storage at %s", settings.redis_url)
        return client
    except Exception as exc:
        logger.warning("Rate limiter: falling back to in-memory storage (%s)", exc)
        return Limiter(key_func=get_remote_address)


limiter = _build_limiter()
