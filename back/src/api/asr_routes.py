"""Volcengine SAUC WebSocket proxy for browser PCM streaming."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from api.deps import get_db_session
from auth.session_keys import SESSION_USER_ID
from db.models import User
from services.asr_proxy import asr_session_manager, parse_asr_ws_json
from settings.config import Settings, get_settings

router = APIRouter(prefix="/api/asr", tags=["asr"])

WS_CLOSE_UNAUTHORIZED = 4401


def _ws_session_user_id(websocket: WebSocket) -> str | None:
    user_id = websocket.session.get(SESSION_USER_ID)
    if not isinstance(user_id, str) or not user_id:
        return None
    return user_id


@router.websocket("/ws")
async def asr_ws(
    websocket: WebSocket,
    db: Annotated[Session, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    user_id = _ws_session_user_id(websocket)
    if user_id is None:
        await websocket.close(code=WS_CLOSE_UNAUTHORIZED, reason="Unauthorized")
        return

    user = db.get(User, user_id)
    if user is None:
        websocket.session.clear()
        await websocket.close(code=WS_CLOSE_UNAUTHORIZED, reason="Unauthorized")
        return

    await websocket.accept()
    await websocket.send_json({"type": "connected", "user_id": user_id})

    try:
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                break
            if message.get("type") != "websocket.receive":
                continue

            if "text" in message and message["text"] is not None:
                raw = message["text"]
                try:
                    payload = parse_asr_ws_json(raw)
                except (ValueError, TypeError):
                    await websocket.send_json(
                        {
                            "type": "asr.error",
                            "code": "invalid_json",
                            "message": "无法解析 JSON 消息",
                        }
                    )
                    continue

                msg_type = payload.get("type")
                if msg_type == "asr.start":
                    await asr_session_manager.handle_start(
                        user_id,
                        websocket,
                        payload,
                        settings=settings,
                    )
                elif msg_type == "asr.stop":
                    await asr_session_manager.handle_stop(user_id, payload)
                else:
                    await websocket.send_json(
                        {
                            "type": "asr.error",
                            "code": "unknown_type",
                            "message": f"未知消息类型：{msg_type}",
                        }
                    )
            elif "bytes" in message and message["bytes"] is not None:
                track = None
                # Optional: future JSON metadata frame before binary; for now route to sole session.
                await asr_session_manager.handle_audio(user_id, message["bytes"], track=track)
    except WebSocketDisconnect:
        pass
    finally:
        await asr_session_manager.unregister(user_id)
