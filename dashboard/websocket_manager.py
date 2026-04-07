from __future__ import annotations

import asyncio

from fastapi import WebSocket


class WebSocketManager:
    def __init__(self):
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop | None = None):
        self._loop = loop or asyncio.get_running_loop()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        async with self._lock:
            self._connections.add(websocket)

    async def disconnect(self, websocket: WebSocket):
        async with self._lock:
            self._connections.discard(websocket)

    async def broadcast(self, message: str):
        async with self._lock:
            connections = list(self._connections)

        dead_connections = []
        for websocket in connections:
            try:
                await websocket.send_text(message)
            except Exception:
                dead_connections.append(websocket)

        if dead_connections:
            async with self._lock:
                for websocket in dead_connections:
                    self._connections.discard(websocket)


ws_manager = WebSocketManager()


def loguru_ws_sink(message):
    text = str(message).rstrip("\n")
    if not text or not ws_manager._connections or ws_manager._loop is None:
        return

    def schedule_broadcast():
        assert ws_manager._loop is not None
        ws_manager._loop.create_task(ws_manager.broadcast(text))

    ws_manager._loop.call_soon_threadsafe(schedule_broadcast)
