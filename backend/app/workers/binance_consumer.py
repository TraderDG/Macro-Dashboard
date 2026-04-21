"""
Entry point: python -m app.workers.binance_consumer
Runs as a separate Docker service (long-lived async process).
"""
import asyncio
import logging
import sys

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

from app.core.config import settings
from app.workers.fetchers.binance_ws import run_binance_ws

if __name__ == "__main__":
    asyncio.run(run_binance_ws(settings.REDIS_URL))
