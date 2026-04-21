from datetime import datetime, timezone, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.core.database import get_db
from app.core.redis_client import get_redis
from app.models.macro import MacroIndicator, YieldCurve, DataIngestionLog

router = APIRouter(prefix="/api/macro", tags=["macro"])


class MacroDataPoint(BaseModel):
    time: datetime
    country_code: str
    indicator: str
    value: float | None
    unit: str | None
    source: str


class YieldPoint(BaseModel):
    time: datetime
    maturity: str
    yield_pct: float | None


# ─── Macro Indicators ─────────────────────────────────────────────────────────

@router.get("/indicators", response_model=list[MacroDataPoint])
async def get_indicators(
    country: str = Query(..., description="ISO3 country code, e.g. USA"),
    indicator: str = Query(..., description="e.g. gdp_growth, cpi_yoy"),
    start: datetime = Query(default=None),
    end: datetime = Query(default=None),
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    cache_key = f"macro:{country}:{indicator}:{start}:{end}"
    cached = await redis.get(cache_key)
    if cached:
        import json
        return json.loads(cached)

    q = select(MacroIndicator).where(
        MacroIndicator.country_code == country.upper(),
        MacroIndicator.indicator == indicator,
    )
    if start:
        q = q.where(MacroIndicator.time >= start)
    if end:
        q = q.where(MacroIndicator.time <= end)
    q = q.order_by(MacroIndicator.time.asc())

    result = await db.execute(q)
    rows = result.scalars().all()
    data = [MacroDataPoint(
        time=r.time, country_code=r.country_code, indicator=r.indicator,
        value=r.value, unit=r.unit, source=r.source,
    ) for r in rows]

    import json
    await redis.setex(cache_key, 3600, json.dumps([d.model_dump(mode="json") for d in data]))
    return data


@router.get("/heatmap")
async def get_heatmap(
    indicator: str = Query(default="gdp_growth"),
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    """Return latest value of an indicator for all countries — for world heatmap."""
    cache_key = f"heatmap:{indicator}"
    cached = await redis.get(cache_key)
    if cached:
        import json
        return json.loads(cached)

    # Get latest value per country
    subq = (
        select(
            MacroIndicator.country_code,
            func.max(MacroIndicator.time).label("max_time"),
        )
        .where(MacroIndicator.indicator == indicator)
        .group_by(MacroIndicator.country_code)
        .subquery()
    )
    q = select(MacroIndicator).join(
        subq,
        (MacroIndicator.country_code == subq.c.country_code)
        & (MacroIndicator.time == subq.c.max_time),
    ).where(MacroIndicator.indicator == indicator)

    result = await db.execute(q)
    rows = result.scalars().all()
    data = [
        {"country_code": r.country_code, "value": r.value, "time": r.time.isoformat()}
        for r in rows
    ]

    import json
    await redis.setex(cache_key, 1800, json.dumps(data))
    return data


@router.get("/country/{country_code}")
async def get_country_profile(
    country_code: str,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    """Full macro profile for a country — latest value of each indicator."""
    cache_key = f"country_profile:{country_code.upper()}"
    cached = await redis.get(cache_key)
    if cached:
        import json
        return json.loads(cached)

    subq = (
        select(
            MacroIndicator.indicator,
            func.max(MacroIndicator.time).label("max_time"),
        )
        .where(MacroIndicator.country_code == country_code.upper())
        .group_by(MacroIndicator.indicator)
        .subquery()
    )
    q = select(MacroIndicator).join(
        subq,
        (MacroIndicator.indicator == subq.c.indicator)
        & (MacroIndicator.time == subq.c.max_time),
    ).where(MacroIndicator.country_code == country_code.upper())

    result = await db.execute(q)
    rows = result.scalars().all()
    profile = {r.indicator: {"value": r.value, "unit": r.unit, "as_of": r.time.isoformat()} for r in rows}

    import json
    await redis.setex(cache_key, 3600, json.dumps(profile))
    return profile


# ─── Yield Curve ──────────────────────────────────────────────────────────────

@router.get("/yields/curve", response_model=list[YieldPoint])
async def get_yield_curve(
    country: str = Query(default="USA"),
    date: datetime = Query(default=None, description="Specific date; defaults to latest"),
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    cache_key = f"yields:{country}:{date}"
    cached = await redis.get(cache_key)
    if cached:
        import json
        return json.loads(cached)

    if date is None:
        # Latest available date
        latest_q = select(func.max(YieldCurve.time)).where(YieldCurve.country_code == country)
        r = await db.execute(latest_q)
        date = r.scalar()
        if not date:
            return []  # no data yet — frontend handles empty gracefully

    q = (
        select(YieldCurve)
        .where(YieldCurve.country_code == country, YieldCurve.time == date)
        .order_by(text("CASE maturity "
                       "WHEN '1m' THEN 1 WHEN '2m' THEN 2 WHEN '3m' THEN 3 "
                       "WHEN '6m' THEN 6 WHEN '1y' THEN 12 WHEN '2y' THEN 24 "
                       "WHEN '3y' THEN 36 WHEN '5y' THEN 60 WHEN '7y' THEN 84 "
                       "WHEN '10y' THEN 120 WHEN '20y' THEN 240 WHEN '30y' THEN 360 END"))
    )
    result = await db.execute(q)
    rows = result.scalars().all()
    data = [YieldPoint(time=r.time, maturity=r.maturity, yield_pct=r.yield_pct) for r in rows]

    import json
    await redis.setex(cache_key, 900, json.dumps([d.model_dump(mode="json") for d in data]))
    return data


@router.get("/yields/history")
async def get_yield_history(
    maturity: str = Query(default="10y"),
    country: str = Query(default="USA"),
    months: int = Query(default=24),
    db: AsyncSession = Depends(get_db),
):
    start = datetime.now().replace(tzinfo=None) - timedelta(days=30 * months)  # tz-naive for SQLite
    q = (
        select(YieldCurve.time, YieldCurve.yield_pct)
        .where(
            YieldCurve.country_code == country,
            YieldCurve.maturity == maturity,
            YieldCurve.time >= start,
        )
        .order_by(YieldCurve.time.asc())
    )
    result = await db.execute(q)
    rows = result.all()
    return [{"time": r.time.isoformat(), "yield_pct": r.yield_pct} for r in rows]


# ─── Ingestion Status ─────────────────────────────────────────────────────────

@router.get("/ingestion/status")
async def get_ingestion_status(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DataIngestionLog).order_by(DataIngestionLog.last_fetched_at.desc()))
    rows = result.scalars().all()
    return [
        {
            "source": r.source,
            "indicator": r.indicator,
            "last_fetched_at": r.last_fetched_at.isoformat() if r.last_fetched_at else None,
            "records_upserted": r.records_upserted,
            "status": r.status,
            "error_msg": r.error_msg,
        }
        for r in rows
    ]
