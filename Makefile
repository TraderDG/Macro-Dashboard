.PHONY: help up down seed seed-demo logs health install dev

help:
	@echo ""
	@echo "  make install     Install frontend dependencies"
	@echo "  make up          Start all Docker services (DB + Redis + Backend + Celery)"
	@echo "  make dev         Start frontend dev server (run after 'make up')"
	@echo "  make seed        Full historical backfill (needs FRED_API_KEY)"
	@echo "  make seed-demo   Demo backfill (no API key needed)"
	@echo "  make logs        Tail backend + worker logs"
	@echo "  make health      Check API health"
	@echo "  make down        Stop all services"
	@echo ""

install:
	cd frontend && npm install

up:
	@echo "Starting Docker services..."
	docker compose up -d --build
	@echo "Waiting 15s for DB to initialise..."
	@sleep 15
	@echo "Services ready."
	@echo "  API:    http://localhost:8000"
	@echo "  Docs:   http://localhost:8000/docs"
	@echo "  Health: http://localhost:8000/health"

dev:
	@echo "Starting frontend at http://localhost:3000"
	cd frontend && npm run dev

seed:
	@echo "Triggering full backfill (FRED + WorldBank + Treasury + Markets)..."
	curl -s http://localhost:8000/api/trigger/backfill | python3 -m json.tool || true
	curl -s http://localhost:8000/api/trigger/backfill-sentiment | python3 -m json.tool || true
	curl -s http://localhost:8000/api/trigger/calendar | python3 -m json.tool || true

seed-demo:
	@echo "Triggering demo backfill (no API key needed)..."
	@echo "  → Market prices (yfinance)..."
	curl -s -X POST http://localhost:8000/api/trigger/markets-only 2>/dev/null || \
	  docker compose exec -T celery_worker celery -A app.workers.celery_app call \
	    app.workers.tasks.fetch_market_latest || true
	@echo "  → World Bank macro data..."
	docker compose exec -T celery_worker celery -A app.workers.celery_app call \
	  app.workers.tasks.fetch_worldbank_latest || true
	@echo "  → US Treasury yields..."
	docker compose exec -T celery_worker celery -A app.workers.celery_app call \
	  app.workers.tasks.fetch_treasury_latest || true
	@echo "  → Sentiment + Calendar..."
	curl -s http://localhost:8000/api/trigger/backfill-sentiment | python3 -m json.tool || true
	curl -s http://localhost:8000/api/trigger/calendar | python3 -m json.tool || true
	@echo "Done. Wait ~2 min for background tasks to complete, then refresh the dashboard."

logs:
	docker compose logs -f backend celery_worker binance_consumer

health:
	@curl -s http://localhost:8000/health | python3 -m json.tool

down:
	docker compose down

reset:
	@echo "WARNING: This will delete all data volumes!"
	docker compose down -v
