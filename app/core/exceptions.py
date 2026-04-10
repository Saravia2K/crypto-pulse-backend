import logging

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.status import (
    HTTP_404_NOT_FOUND,
    HTTP_429_TOO_MANY_REQUESTS,
    HTTP_502_BAD_GATEWAY,
)

logger = logging.getLogger(__name__)


class CryptocurrencyNotFound(Exception):
    """Raised when the requested cryptocurrency does not exist in CoinCap."""

    def __init__(self, crypto_id: str) -> None:
        self.crypto_id = crypto_id
        super().__init__(f"Cryptocurrency '{crypto_id}' not found")


class ExternalAPIError(Exception):
    """Raised when the CoinCap API returns an unexpected error."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------

async def cryptocurrency_not_found_handler(
    request: Request, exc: CryptocurrencyNotFound
) -> JSONResponse:
    return JSONResponse(
        status_code=HTTP_404_NOT_FOUND,
        content={
            "error": "not_found",
            "message": str(exc),
            "id": exc.crypto_id,
        },
    )


async def external_api_error_handler(
    request: Request, exc: ExternalAPIError
) -> JSONResponse:
    logger.error("External API error: %s", exc)
    return JSONResponse(
        status_code=HTTP_502_BAD_GATEWAY,
        content={
            "error": "external_api_error",
            "message": str(exc),
        },
    )


async def rate_limit_exceeded_handler(
    request: Request, exc: RateLimitExceeded
) -> JSONResponse:
    retry_after = getattr(exc, "retry_after", 60)
    return JSONResponse(
        status_code=HTTP_429_TOO_MANY_REQUESTS,
        content={
            "error": "rate_limit_exceeded",
            "message": "Too many requests. Please try again later.",
        },
        headers={"Retry-After": str(retry_after)},
    )
