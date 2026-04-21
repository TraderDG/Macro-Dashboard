from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.core.database import get_db
from app.core.redis_client import get_redis
from app.models.macro import MarketPrice

router = APIRouter(prefix="/api/markets", tags=["markets"])


class PriceBar(BaseModel):
    time: datetime
    symbol: str
    open: float | None
    high: float | None
    low: float | None
    close: float | None
    volume: float | None


@router.get("/overview")
async def get_market_overview(
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    """Latest price snapshot for all tracked symbols."""
    cache_key = "markets:overview"
    cached = await redis.get(cache_key)
    if cached:
        import json
        return json.loads(cached)

    subq = (
        select(MarketPrice.symbol, func.max(MarketPrice.time).label("max_time"))
        .group_by(MarketPrice.symbol)
        .subquery()
    )
    q = select(MarketPrice).join(
        subq,
        (MarketPrice.symbol == subq.c.symbol) & (MarketPrice.time == subq.c.max_time),
    )
    result = await db.execute(q)
    rows = result.scalars().all()
    data = [
        {
            "symbol": r.symbol,
            "asset_class": r.asset_class,
            "close": r.close,
            "open": r.open,
            "change_pct": round((r.close - r.open) / r.open * 100, 2) if r.open else None,
            "time": r.time.isoformat(),
        }
        for r in rows
    ]

    import json
    await redis.setex(cache_key, 300, json.dumps(data))
    return data


@router.get("/ohlcv/{symbol}", response_model=list[PriceBar])
async def get_ohlcv(
    symbol: str,
    days: int = Query(default=365, le=730),
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    cache_key = f"ohlcv:{symbol}:{days}"
    cached = await redis.get(cache_key)
    if cached:
        import json
        return json.loads(cached)

    start = datetime.now(timezone.utc) - timedelta(days=days)
    q = (
        select(MarketPrice)
        .where(MarketPrice.symbol == symbol.upper(), MarketPrice.time >= start)
        .order_by(MarketPrice.time.asc())
    )
    result = await db.execute(q)
    rows = result.scalars().all()
    data = [
        PriceBar(
            time=r.time, symbol=r.symbol,
            open=r.open, high=r.high, low=r.low, close=r.close, volume=r.volume,
        )
        for r in rows
    ]

    import json
    await redis.setex(cache_key, 900, json.dumps([d.model_dump(mode="json") for d in data]))
    return data


@router.get("/by-class/{asset_class}")
async def get_by_asset_class(
    asset_class: str,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    """Latest prices grouped by asset class (equity, forex, commodity, crypto)."""
    cache_key = f"markets:class:{asset_class}"
    cached = await redis.get(cache_key)
    if cached:
        import json
        return json.loads(cached)

    subq = (
        select(MarketPrice.symbol, func.max(MarketPrice.time).label("max_time"))
        .where(MarketPrice.asset_class == asset_class.lower())
        .group_by(MarketPrice.symbol)
        .subquery()
    )
    q = select(MarketPrice).join(
        subq,
        (MarketPrice.symbol == subq.c.symbol) & (MarketPrice.time == subq.c.max_time),
    )
    result = await db.execute(q)
    rows = result.scalars().all()
    data = [
        {
            "symbol": r.symbol,
            "close": r.close,
            "change_pct": round((r.close - r.open) / r.open * 100, 2) if r.open else None,
            "time": r.time.isoformat(),
        }
        for r in rows
    ]

    import json
    await redis.setex(cache_key, 300, json.dumps(data))
    return data
