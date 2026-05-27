"""Upstream WebSocket client for Volcengine SAUC."""

from __future__ import annotations

import uuid
from typing import Protocol

import websockets
from websockets.asyncio.client import ClientConnection

from services.volc_asr.protocol import (
    VolcAsrResponse,
    build_audio_only_request,
    build_full_client_request,
    parse_response,
)
from settings.config import Settings


class VolcAsrClientFactory(Protocol):
    def __call__(self, settings: Settings) -> VolcAsrClient:
        ...


class VolcAsrClient:
    """One upstream SAUC session (connect → full request → audio stream)."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._seq = 1
        self._ws: ClientConnection | None = None

    @property
    def connected(self) -> bool:
        return self._ws is not None

    def _auth_headers(self) -> dict[str, str]:
        access_key = (self._settings.VOLC_ASR_ACCESS_KEY or "").strip()
        app_key = (self._settings.VOLC_ASR_APP_KEY or access_key).strip()
        return {
            "X-Api-Resource-Id": self._settings.VOLC_ASR_RESOURCE_ID,
            "X-Api-Request-Id": str(uuid.uuid4()),
            "X-Api-Access-Key": access_key,
            "X-Api-App-Key": app_key,
        }

    async def connect(self) -> None:
        if self._ws is not None:
            return
        self._seq = 1
        self._ws = await websockets.connect(
            self._settings.VOLC_ASR_WS_URL,
            additional_headers=self._auth_headers(),
        )

    async def send_full_request(self, user_id: str) -> VolcAsrResponse | None:
        if self._ws is None:
            raise RuntimeError("upstream not connected")
        frame = build_full_client_request(self._seq, user_id)
        self._seq += 1
        await self._ws.send(frame)
        raw = await self._ws.recv(decode=False)
        if isinstance(raw, str):
            return None
        return parse_response(raw)

    async def send_audio(self, pcm: bytes, *, is_last: bool = False) -> None:
        if self._ws is None:
            raise RuntimeError("upstream not connected")
        frame = build_audio_only_request(self._seq, pcm, is_last=is_last)
        if not is_last:
            self._seq += 1
        await self._ws.send(frame)

    async def recv_response(self) -> VolcAsrResponse | None:
        if self._ws is None:
            return None
        raw = await self._ws.recv(decode=False)
        if isinstance(raw, str):
            return None
        return parse_response(raw)

    async def close(self) -> None:
        if self._ws is None:
            return
        try:
            await self._ws.close()
        finally:
            self._ws = None


def default_volc_asr_client_factory(settings: Settings) -> VolcAsrClient:
    return VolcAsrClient(settings)
