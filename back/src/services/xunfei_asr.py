"""Xunfei streaming ASR WebSocket client."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import datetime, timezone
from email.utils import format_datetime
from typing import Any
from urllib.parse import urlencode, urlparse

import websockets
from websockets.asyncio.client import ClientConnection

from settings.config import Settings

STATUS_FIRST_FRAME = 0
STATUS_CONTINUE_FRAME = 1
STATUS_LAST_FRAME = 2


def build_xunfei_auth_url(settings: Settings, *, now: datetime | None = None) -> str:
    """Build authenticated Xunfei iat websocket URL."""
    api_key = (settings.XUNFEI_ASR_API_KEY or "").strip()
    api_secret = (settings.XUNFEI_ASR_API_SECRET or "").strip()
    if not api_key or not api_secret:
        raise ValueError("Xunfei ASR credentials are missing")

    parsed = urlparse(settings.XUNFEI_ASR_WS_URL)
    host = parsed.netloc
    path = parsed.path or "/v2/iat"
    date = format_datetime(now or datetime.now(timezone.utc), usegmt=True)
    signature_origin = f"host: {host}\ndate: {date}\nGET {path} HTTP/1.1"
    signature_sha = hmac.new(
        api_secret.encode("utf-8"),
        signature_origin.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    signature = base64.b64encode(signature_sha).decode("utf-8")
    authorization_origin = (
        f'api_key="{api_key}", algorithm="hmac-sha256", '
        f'headers="host date request-line", signature="{signature}"'
    )
    authorization = base64.b64encode(authorization_origin.encode("utf-8")).decode("utf-8")
    query = urlencode({"authorization": authorization, "date": date, "host": host})
    return f"{settings.XUNFEI_ASR_WS_URL}?{query}"


def extract_xunfei_text(payload: dict[str, Any]) -> tuple[str, bool]:
    """Return recognized text and whether this is the final frame."""
    data = payload.get("data")
    if not isinstance(data, dict):
        return "", False
    result = data.get("result")
    if not isinstance(result, dict):
        return "", data.get("status") == STATUS_LAST_FRAME

    words: list[str] = []
    for ws_item in result.get("ws") or []:
        if not isinstance(ws_item, dict):
            continue
        for cw_item in ws_item.get("cw") or []:
            if not isinstance(cw_item, dict):
                continue
            word = cw_item.get("w")
            if isinstance(word, str):
                words.append(word)
    return "".join(words).strip(), data.get("status") == STATUS_LAST_FRAME


class XunfeiAsrClient:
    """Thin async client for Xunfei iat websocket."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._ws: ClientConnection | None = None
        self._sent_first = False

    async def connect(self) -> None:
        self._ws = await websockets.connect(build_xunfei_auth_url(self._settings))

    async def send_audio(self, pcm: bytes, *, is_last: bool = False) -> None:
        if self._ws is None:
            raise RuntimeError("Xunfei websocket is not connected")

        status = STATUS_LAST_FRAME if is_last else (
            STATUS_FIRST_FRAME if not self._sent_first else STATUS_CONTINUE_FRAME
        )
        payload: dict[str, Any] = {
            "data": {
                "status": status,
                "format": "audio/L16;rate=16000",
                "encoding": "raw",
                "audio": base64.b64encode(pcm).decode("utf-8"),
            }
        }
        if not self._sent_first:
            payload["common"] = {"app_id": (self._settings.XUNFEI_ASR_APP_ID or "").strip()}
            payload["business"] = {
                "language": "zh_cn",
                "domain": "iat",
                "accent": "mandarin",
                "vad_eos": 5000,
            }
            self._sent_first = True

        await self._ws.send(json.dumps(payload, ensure_ascii=False))

    async def recv_response(self) -> tuple[str, bool] | None:
        if self._ws is None:
            return None
        raw = await self._ws.recv()
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            return "", False
        code = payload.get("code", 0)
        if code not in (0, "0"):
            message = payload.get("message") or payload.get("desc") or code
            raise RuntimeError(f"Xunfei ASR error: {message}")
        return extract_xunfei_text(payload)

    async def close(self) -> None:
        if self._ws is not None:
            await self._ws.close()
            self._ws = None
