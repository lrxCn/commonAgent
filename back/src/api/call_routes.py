"""WebRTC call signaling: peers list and WebSocket relay."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.deps import get_db_session, require_current_user
from auth.session_keys import SESSION_USER_ID
from db.models import User
from services.call_signaling import call_signaling_hub, list_call_peers, parse_ws_json

router = APIRouter(prefix="/api/calls", tags=["calls"])

WS_CLOSE_UNAUTHORIZED = 4401


class CallPeerItem(BaseModel):
    user_id: str
    username: str
    display_name: str


class CallPeersResponse(BaseModel):
    items: list[CallPeerItem]


@router.get("/peers", response_model=CallPeersResponse)
def get_call_peers(
    user: Annotated[User, Depends(require_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> CallPeersResponse:
    items = list_call_peers(db, user.user_id)
    return CallPeersResponse(items=[CallPeerItem.model_validate(item) for item in items])


def _ws_session_user_id(websocket: WebSocket) -> str | None:
    user_id = websocket.session.get(SESSION_USER_ID)
    if not isinstance(user_id, str) or not user_id:
        return None
    return user_id


@router.websocket("/ws")
async def call_signaling_ws(
    websocket: WebSocket,
    db: Annotated[Session, Depends(get_db_session)],
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
    await call_signaling_hub.register(user_id, websocket)
    await websocket.send_json({"type": "connected", "user_id": user_id})

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                message = parse_ws_json(raw)
            except (ValueError, TypeError):
                await websocket.send_json(
                    {
                        "type": "error",
                        "code": "invalid_json",
                        "message": "无法解析 JSON 消息",
                    }
                )
                continue

            await call_signaling_hub.handle_message(user_id, message, db=db)
    except WebSocketDisconnect:
        pass
    finally:
        await call_signaling_hub.unregister(user_id, websocket)
