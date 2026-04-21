from celery import Celery
from celery.schedules import crontab
from app.core.config import settings

celery_app = Celery(
    "macro_dashboard",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.workers.tasks", "app.workers.tasks_phase2"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,

    beat_schedule={
        # ── Full historical backfill (run once on deploy via separate command) ──
        # Triggered manually: celery -A app.workers.celery_app call app.workers.tasks.backfill_all

        # ── Daily updates ─────────────────────────────────────────────────────
        "daily-fred-update": {
            "task": "app.workers.tasks.fetch_fred_latest",
            "schedule": crontab(hour=6, minute=0),    # 06:00 UTC daily
        },
        "daily-worldbank-update": {
            "task": "app.workers.tasks.fetch_worldbank_latest",
            "schedule": crontab(hour=6, minute=30),
        },
        "daily-yields-update": {
            "task": "app.workers.tasks.fetch_treasury_latest",
            "schedule": crontab(hour=7, minute=0),
        },

        # ── Every 15 minutes (market hours) ───────────────────────────────────
        "market-prices-update": {
            "task": "app.workers.tasks.fetch_market_latest",
            "schedule": crontab(minute="*/15"),
        },

        # ── Phase 2: Sentiment (every 4 hours) ────────────────────────────────
        "fear-greed-update": {
            "task": "app.workers.tasks_phase2.fetch_fear_greed",
            "schedule": crontab(minute=0, hour="*/4"),
        },
        "aaii-sentiment-update": {
            "task": "app.workers.tasks_phase2.fetch_aaii_sentiment",
            "schedule": crontab(hour=8, minute=0, day_of_week="friday"),  # AAII publishes Thursdays
        },

        # ── Phase 2: News (every 30 minutes) ──────────────────────────────────
        "news-update": {
            "task": "app.workers.tasks_phase2.fetch_news",
            "schedule": crontab(minute="*/30"),
        },

        # ── Phase 2: Economic calendar (daily) ────────────────────────────────
        "calendar-update": {
            "task": "app.workers.tasks_phase2.fetch_economic_calendar",
            "schedule": crontab(hour=5, minute=30),
        },
    },
)
