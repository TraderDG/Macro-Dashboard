import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import engine, Base
from app.core.redis_client import close_redis
from app.api.macro import router as macro_router
from app.api.markets import router as markets_router
from app.api.websocket import router as ws_router
from app.api.sentiment import router as sentiment_router

logger = logging.getLogger(__name__)


async def _init_db_with_retry(max_attempts: int = 10, delay: int = 5):
    """Create tables with retries — tolerates DB not being ready at startup."""
    for attempt in range(1, max_attempts + 1):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables ready")
            return
        except Exception as e:
            logger.warning(f"DB not ready (attempt {attempt}/{max_attempts}): {e}")
            if attempt < max_attempts:
                await asyncio.sleep(delay)
    logger.error("Could not connect to DB after retries — continuing without table creation")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Init DB in background so health check passes immediately
    asyncio.create_task(_init_db_with_retry())
    yield
    await close_redis()
    await engine.dispose()


app = FastAPI(
    title="Global Macro Dashboard API",
    version="1.0.0",
    description="Bloomberg-style global macro data API",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
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
    return {"status": "ok", "version": "1.0.0"}


@app.get("/api/trigger/backfill")
async def trigger_backfill():
    from app.workers.tasks import backfill_all
    task = backfill_all.delay()
    return {"task_id": task.id, "status": "queued"}


@app.get("/api/trigger/backfill-sentiment")
async def trigger_backfill_sentiment():
    from app.workers.tasks_phase2 import backfill_sentiment
    task = backfill_sentiment.delay()
    return {"task_id": task.id, "status": "queued"}


@app.get("/api/trigger/calendar")
async def trigger_calendar():
    from app.workers.tasks_phase2 import fetch_economic_calendar
    task = fetch_economic_calendar.delay()
    return {"task_id": task.id, "status": "queued"}


@app.get("/api/trigger/markets-only")
async def trigger_markets_only():
    """Demo-mode seed: market prices + WB + Treasury (no FRED key needed)."""
    from app.workers.tasks import fetch_market_latest, fetch_worldbank_latest, fetch_treasury_latest
    t1 = fetch_market_latest.delay()
    t2 = fetch_worldbank_latest.delay()
    t3 = fetch_treasury_latest.delay()
    return {"tasks": [t1.id, t2.id, t3.id], "status": "queued"}
