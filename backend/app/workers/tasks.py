"""
Celery tasks (+ standalone functions used by main_local.py).
Uses db_utils.upsert — compatible with both PostgreSQL and SQLite.
"""
import logging
from datetime import datetime, timezone
from typing import Any

from app.core.config import settings
from app.core.db_utils import upsert

logger = logging.getLogger(__name__)


def _get_sync_session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    engine = create_engine(settings.DATABASE_URL_SYNC, pool_pre_ping=True)
    Session = sessionmaker(bind=engine)
    return Session(), engine


# ─── Upsert helpers (called by tasks AND main_local.py directly) ──────────────

def _upsert_macro_records(records: list[dict[str, Any]]) -> int:
    if not records:
        return 0
    session, engine = _get_sync_session()
    try:
        from app.models.macro import MacroIndicator
        return upsert(
            session, MacroIndicator.__table__, records,
            index_elements=["time", "country_code", "indicator", "source"],
            update_cols=["value", "created_at"],
        )
    finally:
        session.close(); engine.dispose()


def _upsert_yield_records(records: list[dict[str, Any]]) -> int:
    if not records:
        return 0
    session, engine = _get_sync_session()
    try:
        from app.models.macro import YieldCurve
        return upsert(
            session, YieldCurve.__table__, records,
            index_elements=["time", "country_code", "maturity"],
            update_cols=["yield_pct", "created_at"],
        )
    finally:
        session.close(); engine.dispose()


def _upsert_price_records(records: list[dict[str, Any]]) -> int:
    if not records:
        return 0
    session, engine = _get_sync_session()
    try:
        from app.models.macro import MarketPrice
        return upsert(
            session, MarketPrice.__table__, records,
            index_elements=["time", "symbol"],
            update_cols=["open", "high", "low", "close", "volume", "created_at"],
        )
    finally:
        session.close(); engine.dispose()


def _log_ingestion(source: str, indicator: str, count: int, error: str | None = None):
    session, engine = _get_sync_session()
    try:
        from app.models.macro import DataIngestionLog
        upsert(
            session, DataIngestionLog.__table__,
            [{
                "source": source, "indicator": indicator,
                "last_fetched_at": datetime.now(timezone.utc),
                "records_upserted": count,
                "status": "failed" if error else "success",
                "error_msg": error,
            }],
            index_elements=["source", "indicator"],
            update_cols=["last_fetched_at", "records_upserted", "status", "error_msg"],
        )
    finally:
        session.close(); engine.dispose()


# ─── Celery tasks ─────────────────────────────────────────────────────────────
# (imported lazily so main_local.py can import this module without Celery)

def _get_celery_app():
    from app.workers.celery_app import celery_app
    return celery_app


def _make_task(name):
    """Decorator factory — only registers with Celery when Celery is available."""
    def decorator(fn):
        try:
            app = _get_celery_app()
            return app.task(name=name, bind=True, max_retries=3)(fn)
        except Exception:
            return fn
    return decorator


@_make_task("app.workers.tasks.fetch_fred_latest")
def fetch_fred_latest(self=None):
    if not settings.FRED_API_KEY:
        logger.warning("FRED_API_KEY not set — skipping")
        return {"status": "skipped"}
    try:
        from app.workers.fetchers.fred_fetcher import FredFetcher
        records = FredFetcher().fetch_latest()
        count = _upsert_macro_records(records)
        _log_ingestion("fred", "all_series", count)
        logger.info(f"FRED: upserted {count} rows")
        return {"status": "ok", "rows": count}
    except Exception as e:
        _log_ingestion("fred", "all_series", 0, str(e))
        if self:
            raise self.retry(exc=e, countdown=60)
        raise


@_make_task("app.workers.tasks.fetch_worldbank_latest")
def fetch_worldbank_latest(self=None):
    try:
        from app.workers.fetchers.worldbank_fetcher import WorldBankFetcher
        records = WorldBankFetcher().fetch_latest()
        count = _upsert_macro_records(records)
        _log_ingestion("worldbank", "all_indicators", count)
        logger.info(f"WorldBank: upserted {count} rows")
        return {"status": "ok", "rows": count}
    except Exception as e:
        _log_ingestion("worldbank", "all_indicators", 0, str(e))
        if self:
            raise self.retry(exc=e, countdown=120)
        raise


@_make_task("app.workers.tasks.fetch_treasury_latest")
def fetch_treasury_latest(self=None):
    try:
        from app.workers.fetchers.treasury_fetcher import TreasuryFetcher
        records = TreasuryFetcher().fetch_latest()
        count = _upsert_yield_records(records)
        _log_ingestion("treasury", "yield_curve", count)
        logger.info(f"Treasury: upserted {count} rows")
        return {"status": "ok", "rows": count}
    except Exception as e:
        _log_ingestion("treasury", "yield_curve", 0, str(e))
        if self:
            raise self.retry(exc=e, countdown=60)
        raise


@_make_task("app.workers.tasks.fetch_market_latest")
def fetch_market_latest(self=None):
    try:
        from app.workers.fetchers.treasury_fetcher import MarketFetcher
        records = MarketFetcher().fetch_latest()
        count = _upsert_price_records(records)
        _log_ingestion("yfinance", "market_prices", count)
        logger.info(f"Markets: upserted {count} rows")
        return {"status": "ok", "rows": count}
    except Exception as e:
        _log_ingestion("yfinance", "market_prices", 0, str(e))
        if self:
            raise self.retry(exc=e, countdown=30)
        raise


def backfill_all():
    """Full historical backfill — called directly in local mode."""
    results = {}
    if settings.FRED_API_KEY:
        try:
            from app.workers.fetchers.fred_fetcher import FredFetcher
            records = FredFetcher().fetch_all(start="2000-01-01")
            results["fred"] = _upsert_macro_records(records)
        except Exception as e:
            logger.error(f"FRED backfill failed: {e}")
            results["fred_error"] = str(e)
    else:
        results["fred"] = "skipped_no_key"

    try:
        from app.workers.fetchers.worldbank_fetcher import WorldBankFetcher
        records = WorldBankFetcher().fetch_all(start_year=2000)
        results["worldbank"] = _upsert_macro_records(records)
    except Exception as e:
        logger.error(f"WorldBank backfill failed: {e}")
        results["worldbank_error"] = str(e)

    try:
        from app.workers.fetchers.treasury_fetcher import TreasuryFetcher
        records = TreasuryFetcher().fetch_range(months_back=24)
        results["treasury"] = _upsert_yield_records(records)
    except Exception as e:
        logger.error(f"Treasury backfill failed: {e}")
        results["treasury_error"] = str(e)

    try:
        from app.workers.fetchers.treasury_fetcher import MarketFetcher
        records = MarketFetcher().fetch_daily(period="2y")
        results["markets"] = _upsert_price_records(records)
    except Exception as e:
        logger.error(f"Markets backfill failed: {e}")
        results["markets_error"] = str(e)

    logger.info(f"Backfill complete: {results}")
    return results
