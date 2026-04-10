"""
CryptoPulse – FastAPI application factory.
"""
import logging
import logging.config
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler as _slowapi_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.core.cache import cache
from app.core.config import settings
from app.core.exceptions import (
    CryptocurrencyNotFound,
    ExternalAPIError,
    cryptocurrency_not_found_handler,
    external_api_error_handler,
    rate_limit_exceeded_handler,
)
from app.core.rate_limiter import limiter
from app.routers import crypto, health
from app.services.coincap import coincap_service

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Starting CryptoPulse API…")
    await cache.connect()
    yield
    logger.info("Shutting down CryptoPulse API…")
    await cache.close()
    await coincap_service.close()


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    app = FastAPI(
        title="CryptoPulse API",
        description=(
            "REST API providing real-time and historical cryptocurrency data "
            "powered by CoinCap."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # Rate limiter state (required by slowapi)
    app.state.limiter = limiter

    # Middlewares
    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception handlers
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
    app.add_exception_handler(CryptocurrencyNotFound, cryptocurrency_not_found_handler)
    app.add_exception_handler(ExternalAPIError, external_api_error_handler)

    # Routers
    app.include_router(health.router)
    app.include_router(crypto.router)

    return app


app = create_app()
