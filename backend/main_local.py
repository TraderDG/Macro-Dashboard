"""
Local mode entry point — runs without Docker, Celery, or Redis.
Uses: SQLite (aiosqlite) + in-memory cache + asyncio background tasks.

Run with:
    uvicorn main_local:app --reload --port 8000
"""
import asyncio
import logging
import os
import sys

# ── Point to SQLite before any app imports ────────────────────────────────────
_DB_FILE = os.path.join(os.path.dirname(__file__), "macro_local.db")
_HERE     = os.path.dirname(os.path.abspath(__file__))
_ROOT_ENV = os.path.join(_HERE, "..", ".env")   # macro-dashboard/.env

# Load root .env first so FRED_API_KEY etc. are in os.environ
try:
    from dotenv import load_dotenv
    load_dotenv(_ROOT_ENV, override=False)
except ImportError:
    pass

# These take priority over .env (SQLite paths override any PostgreSQL URL)
os.environ["DATABASE_URL"]      = f"sqlite+aiosqlite:///{_DB_FILE}"
os.environ["DATABASE_URL_SYNC"] = f"sqlite:///{_DB_FILE}"
os.environ.setdefault("REDIS_URL",    "memory://")
os.environ.setdefault("APP_ENV",      "development")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000")

# ── Patch redis_client to use in-memory cache ─────────────────────────────────
from app.core.local_cache import get_local_cache

import app.core.redis_client as _rc
_rc._redis = get_local_cache()          # type: ignore

async def _patched_get_redis():
    return get_local_cache()

async def _patched_close_redis():
    pass

_rc.get_redis   = _patched_get_redis    # type: ignore
_rc.close_redis = _patched_close_redis  # type: ignore

# ── Now import the app (uses patched redis + SQLite URL) ──────────────────────
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import engine, Base
from app.api.macro      import router as macro_router
from app.api.markets    import router as markets_router
from app.api.websocket  import router as ws_router
from app.api.sentiment  import router as sentiment_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("main_local")


# ─── Background seeding ───────────────────────────────────────────────────────

async def _run_in_thread(fn, *args):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, fn, *args)


async def _seed_all():
    """Fetch data in background threads so the API stays responsive."""
    from app.workers.tasks import (
        fetch_fred_latest, fetch_worldbank_latest,
        fetch_treasury_latest, fetch_market_latest,
    )
    from app.workers.tasks_phase2 import (
        fetch_fear_greed, fetch_news, fetch_economic_calendar,
    )

    logger.info("═══ Starting initial data fetch ═══")

    # Markets & yields first (fastest)
    try:
        logger.info("Fetching market prices (yfinance 2y)…")
        from app.workers.fetchers.treasury_fetcher import MarketFetcher
        from app.workers.tasks import _upsert_price_records, _log_ingestion
        records = await _run_in_thread(MarketFetcher().fetch_daily, "2y")
        count = await _run_in_thread(_upsert_price_records, records)
        await _run_in_thread(_log_ingestion, "yfinance", "backfill", count)
        logger.info(f"  → Markets: {count} rows")
    except Exception as e:
        logger.error(f"  → Markets failed: {e}")

    try:
        logger.info("Fetching US Treasury yield curve…")
        from app.workers.fetchers.treasury_fetcher import TreasuryFetcher
        from app.workers.tasks import _upsert_yield_records
        records = await _run_in_thread(TreasuryFetcher().fetch_range, 24)
        count = await _run_in_thread(_upsert_yield_records, records)
        logger.info(f"  → Treasury: {count} rows")
    except Exception as e:
        logger.error(f"  → Treasury failed: {e}")

    # FRED (if key set)
    if settings.FRED_API_KEY:
        try:
            logger.info("Fetching FRED series (2000→today)…")
            from app.workers.fetchers.fred_fetcher import FredFetcher
            from app.workers.tasks import _upsert_macro_records
            records = await _run_in_thread(FredFetcher().fetch_all, "2000-01-01")
            count = await _run_in_thread(_upsert_macro_records, records)
            logger.info(f"  → FRED: {count} rows")
        except Exception as e:
            logger.error(f"  → FRED failed: {e}")
    else:
        logger.warning("  → FRED skipped (no API key)")

    # World Bank
    try:
        logger.info("Fetching World Bank macro data…")
        from app.workers.fetchers.worldbank_fetcher import WorldBankFetcher
        from app.workers.tasks import _upsert_macro_records
        records = await _run_in_thread(WorldBankFetcher().fetch_all, 2000)
        count = await _run_in_thread(_upsert_macro_records, records)
        logger.info(f"  → WorldBank: {count} rows")
    except Exception as e:
        logger.error(f"  → WorldBank failed: {e}")

    # Sentiment + Calendar
    try:
        logger.info("Fetching Fear & Greed…")
        await _run_in_thread(fetch_fear_greed)
    except Exception as e:
        logger.error(f"  → Fear & Greed failed: {e}")

    try:
        logger.info("Fetching news headlines…")
        await _run_in_thread(fetch_news)
    except Exception as e:
        logger.error(f"  → News failed: {e}")

    try:
        logger.info("Fetching economic calendar…")
        await _run_in_thread(fetch_economic_calendar)
    except Exception as e:
        logger.error(f"  → Calendar failed: {e}")

    logger.info("═══ Initial data fetch complete ═══")


async def _periodic_refresh():
    """Refresh market prices every 15 min and other data daily."""
    from app.workers.fetchers.treasury_fetcher import MarketFetcher
    from app.workers.tasks import _upsert_price_records, _log_ingestion

    while True:
        await asyncio.sleep(15 * 60)
        try:
            records = await _run_in_thread(MarketFetcher().fetch_latest)
            count = await _run_in_thread(_upsert_price_records, records)
            logger.info(f"[refresh] Markets: {count} rows")
        except Exception as e:
            logger.warning(f"[refresh] Markets failed: {e}")


# ─── Lifespan ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create all SQLite tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("SQLite tables ready")

    # Check if DB already has data (skip seed on restarts)
    async with engine.connect() as conn:
        from sqlalchemy import text
        row = await conn.execute(text("SELECT COUNT(*) FROM market_prices"))
        existing = row.scalar() or 0

    if existing == 0:
        logger.info("Empty database — starting background seed…")
        asyncio.create_task(_seed_all())
    else:
        logger.info(f"Database has {existing} price rows — skipping full seed")
        asyncio.create_task(_periodic_refresh())

    yield
    await engine.dispose()


# ─── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Macro Terminal (Local Mode)",
    version="1.0.0",
    description="Bloomberg-style macro dashboard — local SQLite mode",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(macro_router)
app.include_router(markets_router)
app.include_router(ws_router)
app.include_router(sentiment_router)


@app.get("/health")
async def health():
    return {"status": "ok", "mode": "local", "db": "sqlite"}


@app.get("/api/trigger/backfill")
async def trigger_backfill():
    asyncio.create_task(_seed_all())
    return {"status": "queued", "mode": "local"}


@app.get("/api/trigger/backfill-sentiment")
async def trigger_backfill_sentiment():
    from app.workers.tasks_phase2 import fetch_fear_greed, fetch_news, fetch_economic_calendar
    async def _run():
        await _run_in_thread(fetch_fear_greed)
        await _run_in_thread(fetch_news)
        await _run_in_thread(fetch_economic_calendar)
    asyncio.create_task(_run())
    return {"status": "queued"}


@app.get("/api/trigger/calendar")
async def trigger_calendar():
    from app.workers.tasks_phase2 import fetch_economic_calendar
    asyncio.create_task(_run_in_thread(fetch_economic_calendar))
    return {"status": "queued"}


@app.get("/api/trigger/markets-only")
async def trigger_markets():
    from app.workers.fetchers.treasury_fetcher import MarketFetcher, TreasuryFetcher
    from app.workers.tasks import _upsert_price_records, _upsert_yield_records
    async def _run():
        r = await _run_in_thread(MarketFetcher().fetch_daily, "2y")
        await _run_in_thread(_upsert_price_records, r)
        r = await _run_in_thread(TreasuryFetcher().fetch_range, 24)
        await _run_in_thread(_upsert_yield_records, r)
    asyncio.create_task(_run())
    return {"status": "queued"}
