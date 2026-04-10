"""
Dual-provider async market data client — no API key required.

  - CryptoCompare  (min-api.cryptocompare.com) → prices, top list, history
  - CoinPaprika    (api.coinpaprika.com)        → coin search

All public methods raise:
  - CryptocurrencyNotFound  when the requested coin does not exist
  - ExternalAPIError        for any other upstream error

The interface is kept compatible with the original service so the routers
don't need to change.
"""
import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.exceptions import CryptocurrencyNotFound, ExternalAPIError

logger = logging.getLogger(__name__)

_CC_BASE = "https://min-api.cryptocompare.com"
_CP_BASE = "https://api.coinpaprika.com/v1"
_TIMEOUT = 15.0

_RETRY_ON = (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError)


# ---------------------------------------------------------------------------
# Data transformers
# ---------------------------------------------------------------------------

def _opt_str(value: Any) -> Optional[str]:
    return None if value is None else str(value)


def _top_item_to_asset(rank: int, item: Dict[str, Any]) -> Dict[str, Any]:
    """Map a /data/top/mktcapfull item to our CryptoAsset schema."""
    info = item.get("CoinInfo") or {}
    raw = ((item.get("RAW") or {}).get("USD")) or {}
    symbol = info.get("Name", "")
    return {
        "id": symbol.lower(),
        "rank": str(rank),
        "symbol": symbol,
        "name": info.get("FullName") or symbol,
        "supply": _opt_str(raw.get("CIRCULATINGSUPPLY")),
        "max_supply": _opt_str(info.get("MaxSupply")),
        "market_cap_usd": _opt_str(raw.get("MKTCAP")),
        "volume_usd_24hr": _opt_str(raw.get("TOTALVOLUME24HTO")),
        "price_usd": _opt_str(raw.get("PRICE")),
        "change_percent_24hr": _opt_str(raw.get("CHANGEPCT24HOUR")),
        "vwap_24hr": None,
        "explorer": None,
    }


def _price_raw_to_asset(
    asset_id: str,
    sym: str,
    raw_usd: Dict[str, Any],
    full_name: str,
    max_supply: Optional[str],
) -> Dict[str, Any]:
    """Map a pricemultifull RAW.{SYM}.USD section to our CryptoAsset schema."""
    # Prefer cross-exchange aggregate volume when available
    vol = raw_usd.get("TOTALVOLUME24HTO") or raw_usd.get("VOLUME24HOURTO")
    return {
        "id": asset_id.lower(),
        "rank": "?",
        "symbol": sym,
        "name": full_name,
        "supply": _opt_str(raw_usd.get("CIRCULATINGSUPPLY") or raw_usd.get("SUPPLY")),
        "max_supply": max_supply,
        "market_cap_usd": _opt_str(raw_usd.get("MKTCAP")),
        "volume_usd_24hr": _opt_str(vol),
        "price_usd": _opt_str(raw_usd.get("PRICE")),
        "change_percent_24hr": _opt_str(raw_usd.get("CHANGEPCT24HOUR")),
        "vwap_24hr": None,
        "explorer": None,
    }


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class CoinCapService:
    """
    Market-data service backed by CryptoCompare + CoinPaprika.
    Named CoinCapService for drop-in compatibility with existing routers.
    """

    def __init__(self) -> None:
        self._cc_client: Optional[httpx.AsyncClient] = None  # CryptoCompare
        self._cp_client: Optional[httpx.AsyncClient] = None  # CoinPaprika

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def _cc(self) -> httpx.AsyncClient:
        if self._cc_client is None or self._cc_client.is_closed:
            self._cc_client = httpx.AsyncClient(
                base_url=_CC_BASE,
                timeout=_TIMEOUT,
                headers={"Accept": "application/json", "Accept-Encoding": "gzip"},
                follow_redirects=True,
            )
        return self._cc_client

    async def _cp(self) -> httpx.AsyncClient:
        if self._cp_client is None or self._cp_client.is_closed:
            self._cp_client = httpx.AsyncClient(
                base_url=_CP_BASE,
                timeout=_TIMEOUT,
                headers={"Accept": "application/json", "Accept-Encoding": "gzip"},
                follow_redirects=True,
            )
        return self._cp_client

    async def close(self) -> None:
        for client in (self._cc_client, self._cp_client):
            if client and not client.is_closed:
                await client.aclose()

    # ------------------------------------------------------------------
    # CryptoCompare HTTP helper
    # ------------------------------------------------------------------

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type(_RETRY_ON),
        reraise=True,
    )
    async def _get_cc(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        sym: Optional[str] = None,
    ) -> Any:
        client = await self._cc()
        try:
            resp = await client.get(path, params=params)
            resp.raise_for_status()
            body = resp.json()

            # CryptoCompare returns HTTP 200 even for logical errors
            if isinstance(body, dict) and body.get("Response") == "Error":
                msg = body.get("Message", "")
                logger.warning("CryptoCompare logical error for %s: %s", path, msg)
                raise CryptocurrencyNotFound(sym or path)

            return body

        except CryptocurrencyNotFound:
            raise
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status == 404:
                raise CryptocurrencyNotFound(sym or path)
            logger.error("CryptoCompare HTTP %s on %s", status, path)
            raise ExternalAPIError(f"CryptoCompare returned HTTP {status}")
        except httpx.TimeoutException:
            logger.warning("CryptoCompare timeout on %s", path)
            raise
        except httpx.RequestError as exc:
            logger.error("CryptoCompare request error: %s", exc)
            raise ExternalAPIError(f"Cannot reach CryptoCompare: {exc}")

    # ------------------------------------------------------------------
    # CoinPaprika HTTP helper
    # ------------------------------------------------------------------

    async def _get_cp(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        client = await self._cp()
        try:
            resp = await client.get(path, params=params)
            if resp.status_code == 404:
                raise CryptocurrencyNotFound(path)
            resp.raise_for_status()
            return resp.json()
        except CryptocurrencyNotFound:
            raise
        except httpx.HTTPStatusError as exc:
            logger.error("CoinPaprika HTTP %s on %s", exc.response.status_code, path)
            raise ExternalAPIError(f"CoinPaprika returned HTTP {exc.response.status_code}")
        except httpx.RequestError as exc:
            logger.error("CoinPaprika request error: %s", exc)
            raise ExternalAPIError(f"Cannot reach CoinPaprika: {exc}")

    # ------------------------------------------------------------------
    # Public API methods
    # ------------------------------------------------------------------

    async def get_assets(
        self, limit: int = 10, offset: int = 0
    ) -> Dict[str, Any]:
        """Top *limit* assets by market cap, using CryptoCompare pagination."""
        page = (offset // limit) + 1
        body = await self._get_cc(
            "/data/top/mktcapfull",
            {"limit": limit, "tsym": "USD", "page": page},
        )
        items: List[Dict[str, Any]] = body.get("Data") or []
        assets = [_top_item_to_asset(offset + i + 1, item) for i, item in enumerate(items)]
        return {"data": assets, "timestamp": int(time.time() * 1000)}

    async def get_asset(self, asset_id: str) -> Dict[str, Any]:
        """Full detail for a single coin identified by lowercase symbol (e.g. 'btc')."""
        sym = asset_id.upper()

        # Fetch price data and general info in parallel
        price_task = self._get_cc(
            "/data/pricemultifull", {"fsyms": sym, "tsyms": "USD"}, sym
        )
        info_task = self._get_cc(
            "/data/coin/generalinfo", {"fsyms": sym, "tsym": "USD"}, sym
        )
        price_result, info_result = await asyncio.gather(
            price_task, info_task, return_exceptions=True
        )

        # If the primary price call failed, propagate
        if isinstance(price_result, CryptocurrencyNotFound):
            raise price_result
        if isinstance(price_result, Exception):
            raise ExternalAPIError(str(price_result))

        raw_usd: Dict[str, Any] = (
            ((price_result.get("RAW") or {}).get(sym) or {}).get("USD") or {}
        )
        if not raw_usd:
            raise CryptocurrencyNotFound(asset_id)

        # Extract metadata from generalinfo (best-effort)
        full_name: str = sym
        max_supply: Optional[str] = None
        if not isinstance(info_result, Exception):
            info_list: List[Dict] = info_result.get("Data") or []
            if info_list:
                coin_info = info_list[0].get("CoinInfo") or {}
                full_name = coin_info.get("FullName") or sym
                max_supply = _opt_str(coin_info.get("MaxSupply"))

        return {
            "data": _price_raw_to_asset(asset_id, sym, raw_usd, full_name, max_supply),
            "timestamp": int(time.time() * 1000),
        }

    async def get_asset_history(
        self, asset_id: str, days: int = 7
    ) -> Dict[str, Any]:
        """Daily closing prices for the last *days* days."""
        sym = asset_id.upper()
        body = await self._get_cc(
            "/data/v2/histoday",
            {"fsym": sym, "tsym": "USD", "limit": days},
            sym,
        )
        # Path: body["Data"]["Data"] → list of OHLCV objects
        points: List[Dict[str, Any]] = (body.get("Data") or {}).get("Data") or []
        history = [
            {
                "price_usd": str(p["close"]),
                # CryptoCompare timestamps are Unix seconds → convert to ms for frontend
                "time": int(p["time"]) * 1000,
                "date": datetime.fromtimestamp(p["time"], tz=timezone.utc).strftime(
                    "%Y-%m-%d"
                ),
            }
            for p in points
            if p.get("close") is not None and p.get("time")
        ]
        return {"data": history}

    async def search_assets(self, query: str) -> Dict[str, Any]:
        """Search by name or symbol using CoinPaprika (free, no key)."""
        body = await self._get_cp(
            "/search",
            {"q": query, "c": "currencies", "limit": 20},
        )
        currencies: List[Dict[str, Any]] = body.get("currencies") or []
        data = [
            {
                "id": (c.get("symbol") or "").lower(),
                "rank": str(c.get("rank") or "?"),
                "symbol": (c.get("symbol") or "").upper(),
                "name": c.get("name", ""),
                "price_usd": None,
                "market_cap_usd": None,
            }
            for c in currencies
            if c.get("is_active")
        ]
        return {"data": data}

    async def ping(self) -> bool:
        """Return True if CryptoCompare is reachable."""
        try:
            await self._get_cc(
                "/data/price", {"fsym": "BTC", "tsyms": "USD"}
            )
            return True
        except Exception:
            return False


# Module-level singleton
coincap_service = CoinCapService()
