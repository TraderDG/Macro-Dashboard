"""
Phase 2 tasks: sentiment, news, economic calendar.
Compatible with both Celery (Docker) and direct calls (local mode).
"""
import logging
from datetime import datetime, timezone

from app.core.config import settings
from app.core.db_utils import upsert

logger = logging.getLogger(__name__)


def _get_sync_session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    engine = create_engine(settings.DATABASE_URL_SYNC, pool_pre_ping=True)
    Session = sessionmaker(bind=engine)
    return Session(), engine


def _upsert_sentiment(records: list[dict]) -> int:
    if not records:
        return 0
    session, engine = _get_sync_session()
    try:
        from app.models.sentiment import SentimentIndicator
        return upsert(
            session, SentimentIndicator.__table__, records,
            index_elements=["time", "indicator", "source"],
            update_cols=["value", "label", "created_at"],
        )
    finally:
        session.close(); engine.dispose()


def _upsert_events(records: list[dict]) -> int:
    if not records:
        return 0
    session, engine = _get_sync_session()
    try:
        from app.models.sentiment import EconomicEvent
        return upsert(
            session, EconomicEvent.__table__, records,
            index_elements=["event_date", "event_name", "country"],
            update_cols=["actual", "forecast", "previous", "created_at"],
        )
    finally:
        session.close(); engine.dispose()


def _insert_news(records: list[dict]) -> int:
    if not records:
        return 0
    session, engine = _get_sync_session()
    try:
        from app.models.sentiment import NewsHeadline
        seen: set[str] = set()
        rows = []
        for r in records:
            url = r.get("url", "") or ""
            if url and url in seen:
                continue
            seen.add(url)
            pub_at = None
            if r.get("published_at"):
                try:
                    from dateutil import parser as dp
                    pub_at = dp.parse(r["published_at"]).replace(tzinfo=timezone.utc)
                except Exception:
                    pass
            rows.append({
                "title": r["title"][:500],
                "url": url or None,
                "source": (r.get("source") or "")[:64],
                "published_at": pub_at,
                "query_tag": (r.get("query") or "")[:64],
            })
        if rows:
            session.execute(NewsHeadline.__table__.insert().values(rows))
            session.commit()
        return len(rows)
    finally:
        session.close(); engine.dispose()


# ─── Task functions (callable directly or via Celery) ────────────────────────

def fetch_fear_greed(self=None):
    from app.workers.fetchers.sentiment_fetcher import FearGreedFetcher
    try:
        fetcher = FearGreedFetcher()
        data = fetcher.fetch()
        records = fetcher.to_db_records(data)
        count = _upsert_sentiment(records)
        logger.info(f"Fear & Greed: {data['score']} ({data['rating']}), {count} rows")
        return {"status": "ok", "score": data["score"], "rows": count}
    except Exception as e:
        logger.error(f"Fear & Greed failed: {e}")
        if self:
            raise self.retry(exc=e, countdown=120)
        return {"status": "error", "error": str(e)}


def fetch_aaii_sentiment(self=None):
    from app.workers.fetchers.sentiment_fetcher import AAIISentimentFetcher
    try:
        records = AAIISentimentFetcher().fetch()
        count = _upsert_sentiment(records)
        logger.info(f"AAII: {count} rows")
        return {"status": "ok", "rows": count}
    except Exception as e:
        logger.error(f"AAII failed: {e}")
        if self:
            raise self.retry(exc=e, countdown=300)
        return {"status": "error", "error": str(e)}


def fetch_news(self=None):
    from app.workers.fetchers.sentiment_fetcher import NewsFetcher
    try:
        articles = NewsFetcher().fetch_gnews(api_key=getattr(settings, "GNEWS_API_KEY", ""))
        count = _insert_news(articles)
        logger.info(f"News: {count} headlines")
        return {"status": "ok", "rows": count}
    except Exception as e:
        logger.error(f"News failed: {e}")
        if self:
            raise self.retry(exc=e, countdown=60)
        return {"status": "error", "error": str(e)}


def fetch_economic_calendar(self=None):
    from app.workers.fetchers.calendar_fetcher import FOMCSchedule, FredCalendarFetcher, InvestingCalendarFetcher
    events = []
    try:
        events.extend(FOMCSchedule().get_upcoming(days_ahead=90))
    except Exception as e:
        logger.warning(f"FOMC schedule failed: {e}")
    if settings.FRED_API_KEY:
        try:
            events.extend(FredCalendarFetcher(settings.FRED_API_KEY).fetch_upcoming(60))
        except Exception as e:
            logger.warning(f"FRED calendar failed: {e}")
    try:
        events.extend(InvestingCalendarFetcher().fetch_week())
    except Exception as e:
        logger.warning(f"Investing calendar failed: {e}")
    count = _upsert_events(events)
    logger.info(f"Calendar: {count} events")
    return {"status": "ok", "rows": count}


def backfill_sentiment():
    results = {}
    results["fear_greed"] = fetch_fear_greed()
    results["aaii"] = fetch_aaii_sentiment()
    return results


# ─── Celery registration (only when Celery is available) ─────────────────────
try:
    from app.workers.celery_app import celery_app

    fetch_fear_greed      = celery_app.task(name="app.workers.tasks_phase2.fetch_fear_greed",      bind=True, max_retries=3)(fetch_fear_greed)
    fetch_aaii_sentiment  = celery_app.task(name="app.workers.tasks_phase2.fetch_aaii_sentiment",  bind=True, max_retries=2)(fetch_aaii_sentiment)
    fetch_news            = celery_app.task(name="app.workers.tasks_phase2.fetch_news",            bind=True, max_retries=3)(fetch_news)
    fetch_economic_calendar = celery_app.task(name="app.workers.tasks_phase2.fetch_economic_calendar", bind=True, max_retries=3)(fetch_economic_calendar)
    backfill_sentiment    = celery_app.task(name="app.workers.tasks_phase2.backfill_sentiment")(backfill_sentiment)
except Exception:
    pass  # Running in local mode without Celery
