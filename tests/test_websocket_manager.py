import asyncio

import pytest

from dashboard.websocket_manager import loguru_ws_sink, ws_manager


@pytest.mark.asyncio
async def test_loguru_ws_sink_schedules_on_bound_loop(monkeypatch):
    done = asyncio.Event()
    messages = []

    async def fake_broadcast(message):
        messages.append(message)
        done.set()

    ws_manager._connections = {object()}
    ws_manager.bind_loop(asyncio.get_running_loop())
    monkeypatch.setattr(ws_manager, "broadcast", fake_broadcast)

    loguru_ws_sink("hello world\n")

    await asyncio.wait_for(done.wait(), timeout=1)
    assert messages == ["hello world"]

    ws_manager._connections.clear()
    ws_manager._loop = None
