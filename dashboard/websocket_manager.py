from __future__ import annotations

import asyncio

from fastapi import WebSocket


class WebSocketManager:
    def __init__(self):
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

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
    if text and ws_manager._connections:
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(ws_manager.broadcast(text))
        except RuntimeError:
            pass
