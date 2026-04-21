# Global Macro Terminal

Bloomberg-style macro dashboard — Phase 1.

## Quick Start

### 1. Setup env
```bash
cp .env.example .env
# Edit .env — add your FRED_API_KEY (free: https://fred.stlouisfed.org/docs/api/api_key.html)
```

### 2. Start backend services
```bash
docker compose up -d --build
```

### 3. Run historical backfill (first time only)
```bash
# Wait ~30s for DB to be ready, then:
docker compose exec celery_worker celery -A app.workers.celery_app call app.workers.tasks.backfill_all
# OR via API:
curl http://localhost:8000/api/trigger/backfill
```

### 4. Start frontend
```bash
cd frontend
npm install
npm run dev
# Open http://localhost:3000
```

## API Docs
- Swagger UI: http://localhost:8000/docs
- Health: http://localhost:8000/health

## Architecture

```
Browser (Next.js :3000)
  ↕ REST + WebSocket
FastAPI (:8000)
  ↕
TimescaleDB (:5432)   Redis (:6379)
  ↑                     ↑
Celery Workers ←── Celery Beat (scheduler)
  ↑
FRED API · World Bank · US Treasury · yfinance
```

## Data Sources
| Source | Data | Frequency |
|--------|------|-----------|
| FRED | US macro (GDP, CPI, rates, VIX, spreads) | Daily 06:00 UTC |
| World Bank | 24 countries × 10 indicators | Daily 06:30 UTC |
| US Treasury | Yield curve (all maturities) | Daily 07:00 UTC |
| yfinance | 18 symbols OHLCV (indices, FX, commodities, crypto) | Every 15min |

## Phase 2 (next)
- Binance WebSocket for real-time crypto ticks
- Fear & Greed scraper
- Macro economic calendar (FOMC, CPI, NFP events)
- OHLCV candlestick chart (TradingView Lightweight Charts)
