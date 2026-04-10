# CryptoPulse Backend

REST API for the CryptoPulse dashboard. Provides real-time and historical
cryptocurrency data sourced from the free [CoinCap v2 API](https://docs.coincap.io/).

## Features

- Real-time prices and market data via CoinCap
- Redis-backed cache with in-memory fallback (no Redis required in dev)
- Per-endpoint rate limiting with `X-RateLimit-*` headers
- Multi-stage Docker build + docker-compose ready

---

## Quick start

### 1. With Docker Compose (recommended)

```bash
# Copy the environment template
cp .env.example .env

# Start API + Redis
docker compose up -d

# Start API + Redis + Redis Commander (UI)
docker compose --profile dev up -d
```

The API is available at **http://localhost:8000**.  
Redis Commander (dev profile) at **http://localhost:8081**.

### 2. Without Docker (local Python)

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env             # adjust REDIS_URL if needed

uvicorn app.main:app --reload --port 8000
```

> Without Redis the app uses an in-memory cache — perfect for local dev.

---

## API Reference

Interactive docs (Swagger UI): **http://localhost:8000/docs**  
ReDoc: **http://localhost:8000/redoc**

| Method | Path | Description | Rate limit |
|--------|------|-------------|------------|
| GET | `/api/crypto/top/{limit}` | Top N cryptos by market cap | 100/min |
| GET | `/api/crypto/search?q=` | Search by name or symbol | 50/min |
| GET | `/api/crypto/{id}` | Full detail for one crypto | 200/min |
| GET | `/api/crypto/{id}/history` | Daily price history (1-30 days) | 100/min |
| GET | `/health` | Service health check | unlimited |
| GET | `/rate-limit/status` | Current rate-limit info for caller | unlimited |

### Example requests

```bash
# Top 10 by market cap
curl http://localhost:8000/api/crypto/top/10

# Bitcoin detail
curl http://localhost:8000/api/crypto/bitcoin

# 14-day history for Ethereum
curl "http://localhost:8000/api/crypto/ethereum/history?days=14"

# Search
curl "http://localhost:8000/api/crypto/search?q=sol"

# Health check
curl http://localhost:8000/health
```

---

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DEBUG` | `False` | Enable debug mode |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `REDIS_URL` | `redis://localhost:6379` | Redis connection string |
| `RATE_LIMIT_REQUESTS` | `100` | Default requests per window |
| `RATE_LIMIT_PERIOD` | `60` | Rate-limit window in seconds |
| `CORS_ORIGINS` | `["http://localhost:3000","http://localhost:5173"]` | Allowed origins |
| `COINCAP_TIMEOUT` | `10.0` | HTTP timeout for CoinCap requests |
| `CACHE_TTL_TOP` | `300` | Cache TTL for /top (seconds) |
| `CACHE_TTL_DETAIL` | `60` | Cache TTL for /{id} (seconds) |
| `CACHE_TTL_HISTORY` | `300` | Cache TTL for /history (seconds) |
| `CACHE_TTL_SEARCH` | `120` | Cache TTL for /search (seconds) |

---

## Running tests

```bash
pip install -r requirements.txt
pytest -v
```

Tests use an in-memory cache and mock all external HTTP calls — no live Redis
or internet connection required.

---

## Project structure

```
app/
├── core/
│   ├── config.py        # Pydantic Settings
│   ├── cache.py         # Redis + in-memory cache manager
│   ├── rate_limiter.py  # slowapi limiter setup
│   └── exceptions.py    # Custom exceptions & handlers
├── routers/
│   ├── crypto.py        # /api/crypto/* endpoints
│   └── health.py        # /health, /rate-limit/status
├── schemas/
│   └── crypto.py        # Pydantic response models
├── services/
│   └── coincap.py       # CoinCap API client (with retry)
└── main.py              # FastAPI app factory
tests/
├── conftest.py
├── test_crypto.py
└── test_health.py
```
