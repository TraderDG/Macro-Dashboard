from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis_client import get_redis
from app.models.sentiment import SentimentIndicator, EconomicEvent, NewsHeadline

router = APIRouter(prefix="/api/sentiment", tags=["sentiment"])


# ─── Fear & Greed ─────────────────────────────────────────────────────────────

@router.get("/fear-greed/latest")
async def get_fear_greed_latest(
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    cache_key = "fear_greed:latest"
    cached = await redis.get(cache_key)
    if cached:
        import json
        return json.loads(cached)

    q = (
        select(SentimentIndicator)
        .where(SentimentIndicator.indicator == "fear_greed_index")
        .order_by(SentimentIndicator.time.desc())
        .limit(1)
    )
    result = await db.execute(q)
    row = result.scalar_one_or_none()

    data = {
        "score": row.value if row else None,
        "label": row.label if row else None,
        "time": row.time.isoformat() if row else None,
    }

    import json
    await redis.setex(cache_key, 1800, json.dumps(data))
    return data


@router.get("/fear-greed/history")
async def get_fear_greed_history(
    days: int = Query(default=90, le=365),
    db: AsyncSession = Depends(get_db),
):
    start = datetime.now(timezone.utc) - timedelta(days=days)
    q = (
        select(SentimentIndicator.time, SentimentIndicator.value, SentimentIndicator.label)
        .where(
            SentimentIndicator.indicator == "fear_greed_index",
            SentimentIndicator.time >= start,
        )
        .order_by(SentimentIndicator.time.asc())
    )
    result = await db.execute(q)
    return [{"time": r.time.isoformat(), "score": r.value, "label": r.label} for r in result.all()]


# ─── AAII Sentiment ───────────────────────────────────────────────────────────

@router.get("/aaii")
async def get_aaii_latest(
    weeks: int = Query(default=52),
    db: AsyncSession = Depends(get_db),
):
    start = datetime.now(timezone.utc) - timedelta(weeks=weeks)
    q = (
        select(SentimentIndicator)
        .where(
            SentimentIndicator.source == "aaii",
            SentimentIndicator.time >= start,
        )
        .order_by(SentimentIndicator.time.asc())
    )
    result = await db.execute(q)
    rows = result.scalars().all()

    grouped: dict[str, list] = {}
    for r in rows:
        key = r.time.isoformat()
        if key not in grouped:
            grouped[key] = {"time": key}
        grouped[key][r.indicator.replace("aaii_", "")] = r.value

    return sorted(grouped.values(), key=lambda x: x["time"])


# ─── Economic Calendar ────────────────────────────────────────────────────────

@router.get("/calendar")
async def get_calendar(
    days_ahead: int = Query(default=30, le=90),
    days_behind: int = Query(default=7, le=30),
    country: str = Query(default=None),
    importance: str = Query(default=None, description="low/medium/high"),
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    cache_key = f"calendar:{days_ahead}:{days_behind}:{country}:{importance}"
    cached = await redis.get(cache_key)
    if cached:
        import json
        return json.loads(cached)

    now = datetime.now(timezone.utc)
    q = select(EconomicEvent).where(
        EconomicEvent.event_date >= now - timedelta(days=days_behind),
        EconomicEvent.event_date <= now + timedelta(days=days_ahead),
    )
    if country:
        q = q.where(EconomicEvent.country == country.upper())
    if importance:
        q = q.where(EconomicEvent.importance == importance.lower())
    q = q.order_by(EconomicEvent.event_date.asc())

    result = await db.execute(q)
    rows = result.scalars().all()
    def _is_past(dt, now):
        if dt is None:
            return False
        naive_now = now.replace(tzinfo=None) if dt.tzinfo is None else now
        return dt < naive_now

    data = [
        {
            "id": r.id,
            "event_date": r.event_date.isoformat(),
            "event_name": r.event_name,
            "country": r.country,
            "importance": r.importance,
            "actual": r.actual,
            "forecast": r.forecast,
            "previous": r.previous,
            "is_past": _is_past(r.event_date, now),
        }
        for r in rows
    ]

    import json
    await redis.setex(cache_key, 900, json.dumps(data))
    return data


# ─── News Headlines ───────────────────────────────────────────────────────────

@router.get("/news")
async def get_news(
    limit: int = Query(default=20, le=50),
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    cache_key = f"news:latest:{limit}"
    cached = await redis.get(cache_key)
    if cached:
        import json
        return json.loads(cached)

    q = (
        select(NewsHeadline)
        .order_by(NewsHeadline.published_at.desc().nullslast())
        .limit(limit)
    )
    result = await db.execute(q)
    rows = result.scalars().all()
    data = [
        {
            "title": r.title,
            "url": r.url,
            "source": r.source,
            "published_at": r.published_at.isoformat() if r.published_at else None,
        }
        for r in rows
    ]

    import json
    await redis.setex(cache_key, 300, json.dumps(data))
    return data


# ─── Live crypto prices from Redis cache ─────────────────────────────────────

@router.get("/crypto/live")
async def get_crypto_live(redis=Depends(get_redis)):
    """Return latest Binance ticks from Redis cache (updated every second)."""
    import json
    symbols = [
        "BTC-USD", "ETH-USD", "BNB-USD", "SOL-USD", "XRP-USD",
        "ADA-USD", "AVAX-USD", "DOGE-USD", "LINK-USD", "MATIC-USD",
    ]
    result = []
    for sym in symbols:
        raw = await redis.get(f"price:{sym}")
        if raw:
            result.append(json.loads(raw))
    return result
