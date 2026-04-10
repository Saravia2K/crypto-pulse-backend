from typing import List, Optional

from pydantic import BaseModel


class CryptoAsset(BaseModel):
    id: str
    rank: str
    symbol: str
    name: str
    supply: Optional[str] = None
    max_supply: Optional[str] = None
    market_cap_usd: Optional[str] = None
    volume_usd_24hr: Optional[str] = None
    price_usd: Optional[str] = None
    change_percent_24hr: Optional[str] = None
    vwap_24hr: Optional[str] = None
    explorer: Optional[str] = None


class TopCryptosResponse(BaseModel):
    data: List[CryptoAsset]
    timestamp: int
    limit: int
    offset: int


class CryptoDetailResponse(BaseModel):
    data: CryptoAsset
    timestamp: int


class HistoryPoint(BaseModel):
    price_usd: str
    time: int
    date: str


class HistoryResponse(BaseModel):
    data: List[HistoryPoint]
    id: str
    days: int


class SearchResult(BaseModel):
    id: str
    rank: str
    symbol: str
    name: str
    price_usd: Optional[str] = None
    market_cap_usd: Optional[str] = None


class SearchResponse(BaseModel):
    data: List[SearchResult]
    query: str
    count: int


class HealthDependency(BaseModel):
    status: str
    detail: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    redis: HealthDependency
    coincap_api: HealthDependency
    timestamp: int


class RateLimitStatusResponse(BaseModel):
    limit: int
    period_seconds: int
    requests_remaining: Optional[int] = None
    reset_at: Optional[int] = None
