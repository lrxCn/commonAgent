"""In-process WebRTC call signaling hub (single-worker demo)."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

from fastapi import WebSocket
from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import User

CallState = Literal["ringing", "accepted", "ended"]


@dataclass
class CallRecord:
    call_id: str
    caller_id: str
    callee_id: str
    state: CallState = "ringing"


@dataclass
class CallSignalingHub:
    """Process-local user connections and call session routing."""

    _connections: dict[str, WebSocket] = field(default_factory=dict)
    _calls: dict[str, CallRecord] = field(default_factory=dict)

    def reset(self) -> None:
        self._connections.clear()
        self._calls.clear()

    def is_online(self, user_id: str) -> bool:
        return user_id in self._connections

    def is_busy(self, user_id: str) -> bool:
        for call in self._calls.values():
            if call.state == "accepted" and user_id in (call.caller_id, call.callee_id):
                return True
        return False

    def _participant_ids(self, call_id: str) -> tuple[str, str] | None:
        call = self._calls.get(call_id)
        if call is None:
            return None
        return call.caller_id, call.callee_id

    def _peer_id(self, call_id: str, user_id: str) -> str | None:
        participants = self._participant_ids(call_id)
        if participants is None:
            return None
        caller_id, callee_id = participants
        if user_id == caller_id:
            return callee_id
        if user_id == callee_id:
            return caller_id
        return None

    async def _send(self, user_id: str, payload: dict[str, Any]) -> None:
        ws = self._connections.get(user_id)
        if ws is None:
            return
        await ws.send_json(payload)

    async def _send_error(
        self,
        user_id: str,
        *,
        code: str,
        message: str,
    ) -> None:
        await self._send(user_id, {"type": "error", "code": code, "message": message})

    async def register(self, user_id: str, websocket: WebSocket) -> None:
        old = self._connections.get(user_id)
        if old is not None and old is not websocket:
            try:
                await old.send_json({"type": "session.replaced"})
            except Exception:
                pass
            try:
                await old.close(code=4000, reason="session replaced")
            except Exception:
                pass
        self._connections[user_id] = websocket

    async def unregister(self, user_id: str, websocket: WebSocket) -> None:
        if self._connections.get(user_id) is not websocket:
            return
        del self._connections[user_id]
        ended_calls: list[str] = []
        for call_id, call in list(self._calls.items()):
            if call.state == "ended":
                continue
            if user_id not in (call.caller_id, call.callee_id):
                continue
            call.state = "ended"
            ended_calls.append(call_id)
            peer_id = self._peer_id(call_id, user_id)
            if peer_id is not None:
                await self._send(
                    peer_id,
                    {
                        "type": "call.ended",
                        "call_id": call_id,
                        "reason": "peer_disconnected",
                    },
                )
        for call_id in ended_calls:
            self._calls.pop(call_id, None)

    async def handle_message(
        self,
        user_id: str,
        message: dict[str, Any],
        *,
        db: Session,
    ) -> None:
        msg_type = message.get("type")
        if not isinstance(msg_type, str):
            await self._send_error(user_id, code="invalid_message", message="缺少 type")
            return

        if msg_type == "call.invite":
            await self._handle_invite(user_id, message, db=db)
        elif msg_type == "call.cancel":
            await self._handle_cancel(user_id, message)
        elif msg_type == "call.accept":
            await self._handle_accept(user_id, message)
        elif msg_type == "call.reject":
            await self._handle_reject(user_id, message)
        elif msg_type == "call.hangup":
            await self._handle_hangup(user_id, message)
        elif msg_type in ("rtc.offer", "rtc.answer", "rtc.ice"):
            await self._handle_rtc(user_id, message, msg_type)
        else:
            await self._send_error(
                user_id,
                code="unknown_type",
                message=f"未知消息类型：{msg_type}",
            )

    async def _handle_invite(
        self,
        caller_id: str,
        message: dict[str, Any],
        *,
        db: Session,
    ) -> None:
        to_user_id = message.get("to_user_id")
        if not isinstance(to_user_id, str) or not to_user_id.strip():
            await self._send_error(
                caller_id,
                code="invalid_target",
                message="to_user_id 无效",
            )
            return

        to_user_id = to_user_id.strip()
        if to_user_id == caller_id:
            await self._send_error(
                caller_id,
                code="invalid_target",
                message="不能呼叫自己",
            )
            return

        callee = db.get(User, to_user_id)
        if callee is None:
            await self._send_error(
                caller_id,
                code="user_not_found",
                message="目标用户不存在",
            )
            return

        call_id = str(uuid.uuid4())
        if not self.is_online(to_user_id):
            await self._send(
                caller_id,
                {
                    "type": "call.failed",
                    "call_id": call_id,
                    "code": "callee_offline",
                },
            )
            return

        if self.is_busy(to_user_id):
            await self._send(
                caller_id,
                {
                    "type": "call.busy",
                    "call_id": call_id,
                },
            )
            return

        caller = db.get(User, caller_id)
        caller_display = caller.display_name if caller else caller_id

        self._calls[call_id] = CallRecord(
            call_id=call_id,
            caller_id=caller_id,
            callee_id=to_user_id,
            state="ringing",
        )

        await self._send(
            to_user_id,
            {
                "type": "call.incoming",
                "call_id": call_id,
                "from_user_id": caller_id,
                "from_display_name": caller_display,
            },
        )
        await self._send(
            caller_id,
            {
                "type": "call.ringing",
                "call_id": call_id,
                "to_user_id": to_user_id,
            },
        )

    async def _handle_cancel(self, user_id: str, message: dict[str, Any]) -> None:
        call_id = message.get("call_id")
        if not isinstance(call_id, str):
            await self._send_error(user_id, code="invalid_call", message="call_id 无效")
            return

        call = self._calls.get(call_id)
        if call is None or call.caller_id != user_id:
            await self._send_error(user_id, code="forbidden", message="无权取消该呼叫")
            return
        if call.state != "ringing":
            await self._send(
                user_id,
                {
                    "type": "call.failed",
                    "call_id": call_id,
                    "code": "invalid_state",
                },
            )
            return

        call.state = "ended"
        payload = {"type": "call.canceled", "call_id": call_id}
        await self._send(call.caller_id, payload)
        await self._send(call.callee_id, payload)
        del self._calls[call_id]

    async def _handle_accept(self, user_id: str, message: dict[str, Any]) -> None:
        call_id = message.get("call_id")
        if not isinstance(call_id, str):
            await self._send_error(user_id, code="invalid_call", message="call_id 无效")
            return

        call = self._calls.get(call_id)
        if call is None or call.callee_id != user_id:
            await self._send_error(user_id, code="forbidden", message="无权接听该呼叫")
            return
        if call.state != "ringing":
            await self._send(
                user_id,
                {
                    "type": "call.failed",
                    "call_id": call_id,
                    "code": "invalid_state",
                },
            )
            return

        call.state = "accepted"
        payload = {"type": "call.accepted", "call_id": call_id}
        await self._send(call.caller_id, payload)
        await self._send(call.callee_id, payload)

    async def _handle_reject(self, user_id: str, message: dict[str, Any]) -> None:
        call_id = message.get("call_id")
        if not isinstance(call_id, str):
            await self._send_error(user_id, code="invalid_call", message="call_id 无效")
            return

        call = self._calls.get(call_id)
        if call is None or call.callee_id != user_id:
            await self._send_error(user_id, code="forbidden", message="无权拒接该呼叫")
            return
        if call.state != "ringing":
            await self._send(
                user_id,
                {
                    "type": "call.failed",
                    "call_id": call_id,
                    "code": "invalid_state",
                },
            )
            return

        call.state = "ended"
        await self._send(call.caller_id, {"type": "call.rejected", "call_id": call_id})
        del self._calls[call_id]

    async def _handle_hangup(self, user_id: str, message: dict[str, Any]) -> None:
        call_id = message.get("call_id")
        if not isinstance(call_id, str):
            await self._send_error(user_id, code="invalid_call", message="call_id 无效")
            return

        call = self._calls.get(call_id)
        if call is None or user_id not in (call.caller_id, call.callee_id):
            await self._send_error(user_id, code="forbidden", message="无权挂断该呼叫")
            return
        if call.state == "ended":
            return

        call.state = "ended"
        payload = {"type": "call.ended", "call_id": call_id, "reason": "hangup"}
        await self._send(call.caller_id, payload)
        await self._send(call.callee_id, payload)
        del self._calls[call_id]

    async def _handle_rtc(
        self,
        user_id: str,
        message: dict[str, Any],
        msg_type: str,
    ) -> None:
        call_id = message.get("call_id")
        if not isinstance(call_id, str):
            await self._send_error(user_id, code="invalid_call", message="call_id 无效")
            return

        call = self._calls.get(call_id)
        if call is None or user_id not in (call.caller_id, call.callee_id):
            await self._send_error(user_id, code="forbidden", message="无权发送 RTC 信令")
            return
        if call.state != "accepted":
            await self._send_error(
                user_id,
                code="invalid_state",
                message="通话尚未建立，无法交换媒体信令",
            )
            return

        peer_id = self._peer_id(call_id, user_id)
        if peer_id is None:
            return

        if msg_type == "rtc.ice":
            candidate = message.get("candidate")
            if not isinstance(candidate, dict):
                await self._send_error(
                    user_id,
                    code="invalid_candidate",
                    message="candidate 无效",
                )
                return
            await self._send(
                peer_id,
                {"type": "rtc.ice", "call_id": call_id, "candidate": candidate},
            )
            return

        sdp = message.get("sdp")
        if not isinstance(sdp, str) or not sdp.strip():
            await self._send_error(user_id, code="invalid_sdp", message="sdp 无效")
            return
        await self._send(
            peer_id,
            {"type": msg_type, "call_id": call_id, "sdp": sdp},
        )


def list_call_peers(db: Session, current_user_id: str) -> list[dict[str, str]]:
    users = db.scalars(
        select(User)
        .where(User.user_id != current_user_id)
        .order_by(User.username.asc())
    ).all()
    return [
        {
            "user_id": user.user_id,
            "username": user.username,
            "display_name": user.display_name,
        }
        for user in users
    ]


def parse_ws_json(raw: str) -> dict[str, Any]:
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("message must be a JSON object")
    return data


call_signaling_hub = CallSignalingHub()
