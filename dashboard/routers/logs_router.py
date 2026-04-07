from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect

from dashboard.auth import get_current_user, ws_auth
from dashboard.schemas import LogResponse
from dashboard.services.log_service import read_log_lines
from dashboard.websocket_manager import ws_manager

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get("", response_model=LogResponse)
def get_logs(
    date: str | None = Query(default=None),
    keyword: str = Query(default=""),
    level: str = Query(default=""),
    tail: int = Query(default=0, ge=0),
    current_user: str = Depends(get_current_user),
):
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")
    try:
        lines = read_log_lines(date, keyword, level, tail)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return LogResponse(date=date, total_lines=len(lines), lines=lines)


@router.websocket("/stream")
async def log_stream(websocket: WebSocket):
    try:
        await ws_auth(websocket)
    except Exception:
        return

    await ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await ws_manager.disconnect(websocket)
