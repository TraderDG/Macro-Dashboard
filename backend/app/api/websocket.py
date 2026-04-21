"""
WebSocket endpoint for real-time price push.
Redis pub/sub → FastAPI WS → Browser.
"""
import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.core.redis_client import get_redis

router = APIRouter(tags=["websocket"])
logger = logging.getLogger(__name__)


@router.websocket("/ws/prices")
async def ws_prices(websocket: WebSocket):
    """Subscribe to live price updates via Redis pub/sub."""
    await websocket.accept()
    redis = await get_redis()
    pubsub = redis.pubsub()
    await pubsub.subscribe("channel:prices")
    logger.info("WS client connected to prices channel")
    try:
        while True:
            message = await asyncio.wait_for(pubsub.get_message(ignore_subscribe_messages=True), timeout=30)
            if message and message["type"] == "message":
                await websocket.send_text(message["data"])
            else:
                await websocket.send_text('{"type":"ping"}')
    except (WebSocketDisconnect, asyncio.TimeoutError):
        pass
    finally:
        await pubsub.unsubscribe("channel:prices")
        await pubsub.close()
        logger.info("WS client disconnected")


@router.websocket("/ws/macro")
async def ws_macro(websocket: WebSocket):
    """Subscribe to macro data updates."""
    await websocket.accept()
    redis = await get_redis()
    pubsub = redis.pubsub()
    await pubsub.subscribe("channel:macro")
    try:
        while True:
            message = await asyncio.wait_for(pubsub.get_message(ignore_subscribe_messages=True), timeout=30)
            if message and message["type"] == "message":
                await websocket.send_text(message["data"])
            else:
                await websocket.send_text('{"type":"ping"}')
    except (WebSocketDisconnect, asyncio.TimeoutError):
        pass
    finally:
        await pubsub.unsubscribe("channel:macro")
        await pubsub.close()
