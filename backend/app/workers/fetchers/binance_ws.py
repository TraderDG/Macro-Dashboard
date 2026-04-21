"""
Binance WebSocket consumer — streams real-time ticker prices for top crypto.
Publishes updates to Redis channel:prices so WS clients receive live ticks.
No API key required.
"""
import asyncio
import json
import logging
from datetime import datetime, timezone

import websockets
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

SYMBOLS = [
    "btcusdt", "ethusdt", "bnbusdt", "solusdt", "xrpusdt",
    "adausdt", "avaxusdt", "dogeusdt", "linkusdt", "maticusdt",
]

# Binance combined stream: up to 1024 streams per connection
STREAM_URL = (
    "wss://stream.binance.com:9443/stream?streams="
    + "/".join(f"{s}@ticker" for s in SYMBOLS)
)


def _normalize_symbol(binance_symbol: str) -> str:
    return binance_symbol.upper().replace("USDT", "-USD")


async def run_binance_ws(redis_url: str):
    """
    Long-running coroutine — connect to Binance, push ticks to Redis.
    Call via: asyncio.run(run_binance_ws(settings.REDIS_URL))
    """
    import redis.asyncio as aioredis

    redis = aioredis.from_url(redis_url, decode_responses=True)

    @retry(stop=stop_after_attempt(10), wait=wait_exponential(multiplier=1, min=2, max=30))
    async def _connect():
        logger.info("Binance WS: connecting...")
        async with websockets.connect(STREAM_URL, ping_interval=20, ping_timeout=20) as ws:
            logger.info("Binance WS: connected")
            async for raw in ws:
                try:
                    envelope = json.loads(raw)
                    data = envelope.get("data", {})
                    if data.get("e") != "24hrTicker":
                        continue

                    symbol = _normalize_symbol(data["s"])
                    payload = {
                        "type": "price_tick",
                        "source": "binance",
                        "symbol": symbol,
                        "price": float(data["c"]),
                        "change_pct": float(data["P"]),
                        "high": float(data["h"]),
                        "low": float(data["l"]),
                        "volume": float(data["v"]),
                        "time": datetime.now(timezone.utc).isoformat(),
                    }

                    # Publish to Redis for WebSocket broadcast
                    await redis.publish("channel:prices", json.dumps(payload))

                    # Cache latest price per symbol (TTL 30s)
                    await redis.setex(f"price:{symbol}", 30, json.dumps(payload))

                except (KeyError, ValueError, json.JSONDecodeError):
                    pass

    try:
        await _connect()
    except Exception as e:
        logger.error(f"Binance WS: fatal error: {e}")
    finally:
        await redis.aclose()
