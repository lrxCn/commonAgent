"""Browser WebSocket ↔ Volcengine SAUC upstream bridge."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Literal

from fastapi import WebSocket

from services.volc_asr.client import VolcAsrClient, default_volc_asr_client_factory
from services.volc_asr.protocol import VolcAsrResponse, pcm_segment_size_bytes
from settings.config import Settings, get_settings

AsrTrack = Literal["local", "remote"]
SessionKey = tuple[str, AsrTrack]

# Volcengine SAUC: wait-for-audio timeout; harmless when the browser never sent PCM.
UPSTREAM_CODE_PACKET_TIMEOUT = 45000081

logger = logging.getLogger(__name__)


def parse_asr_ws_json(raw: str) -> dict[str, Any]:
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("message must be a JSON object")
    return data


def credentials_configured(settings: Settings) -> bool:
    return bool((settings.VOLC_ASR_ACCESS_KEY or "").strip())


def extract_transcript_events(
    payload_msg: dict[str, Any] | None,
    *,
    track: AsrTrack,
) -> list[dict[str, Any]]:
    if not payload_msg:
        return []

    result = payload_msg.get("result")
    if not isinstance(result, dict):
        return []

    events: list[dict[str, Any]] = []
    utterances = result.get("utterances")
    if isinstance(utterances, list) and utterances:
        for item in utterances:
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            if not isinstance(text, str) or not text.strip():
                continue
            base = {
                "track": track,
                "text": text.strip(),
                "start_time": item.get("start_time"),
                "end_time": item.get("end_time"),
            }
            if item.get("definite") is True:
                events.append({"type": "asr.final", **base})
            else:
                events.append({"type": "asr.partial", **base})
        return events

    text = result.get("text")
    if isinstance(text, str) and text.strip():
        events.append(
            {
                "type": "asr.partial",
                "track": track,
                "text": text.strip(),
            }
        )
    return events


@dataclass
class AsrTrackSession:
    user_id: str
    track: AsrTrack
    websocket: WebSocket
    settings: Settings
    scene: str = "call"
    call_id: str | None = None
    client_factory: Any = field(default=default_volc_asr_client_factory)
    upstream: VolcAsrClient | None = None
    audio_buffer: bytearray = field(default_factory=bytearray)
    closed: bool = False
    has_received_pcm: bool = False

    @property
    def segment_size(self) -> int:
        return pcm_segment_size_bytes(segment_ms=self.settings.VOLC_ASR_SEGMENT_MS)

    async def send_json(self, payload: dict[str, Any]) -> None:
        if self.closed:
            return
        await self.websocket.send_json(payload)

    async def send_error(self, *, code: str, message: str) -> None:
        await self.send_json({"type": "asr.error", "code": code, "message": message})

    async def start(self, message: dict[str, Any]) -> None:
        scene = message.get("scene")
        if scene != "call":
            await self.send_error(code="invalid_scene", message="scene 必须为 call")
            return

        track = message.get("track")
        if track not in ("local", "remote"):
            await self.send_error(code="invalid_track", message="track 必须为 local 或 remote")
            return
        self.track = track

        call_id = message.get("call_id")
        if isinstance(call_id, str) and call_id.strip():
            self.call_id = call_id.strip()

        if not credentials_configured(self.settings):
            await self.send_error(code="credentials_missing", message="ASR 凭证未配置")
            return

        self.upstream = self.client_factory(self.settings)
        try:
            await self.upstream.connect()
            full_response = await self.upstream.send_full_request(self.user_id)
        except Exception as exc:
            logger.warning(
                "upstream connect/full_request failed track=%s error_type=%s message=%s",
                self.track,
                type(exc).__name__,
                exc,
            )
            await self.send_error(code="upstream_connect_failed", message="连接语音识别服务失败")
            await self.cleanup()
            return

        if full_response is not None and full_response.code != 0:
            logger.warning(
                "upstream full_request rejected track=%s upstream_code=%s",
                self.track,
                full_response.code,
            )
            await self.send_error(
                code="upstream_error",
                message=f"上游错误 code={full_response.code}",
            )
            await self.cleanup()
            return

    async def append_audio(self, pcm: bytes) -> None:
        if self.closed or self.upstream is None:
            return
        if pcm:
            self.has_received_pcm = True
        self.audio_buffer.extend(pcm)
        while len(self.audio_buffer) >= self.segment_size:
            segment = bytes(self.audio_buffer[: self.segment_size])
            del self.audio_buffer[: self.segment_size]
            await self.upstream.send_audio(segment, is_last=False)
            await self._poll_upstream(timeout=0.05)

    async def stop(self) -> None:
        if self.closed or self.upstream is None:
            return
        if not self.has_received_pcm:
            await self.cleanup()
            return

        remainder = bytes(self.audio_buffer)
        self.audio_buffer.clear()
        if remainder:
            await self.upstream.send_audio(remainder, is_last=True)
        else:
            await self.upstream.send_audio(b"\x00\x00", is_last=True)
        ended = await self._poll_upstream(timeout=2.0, wait_last=True)
        if ended:
            await self.send_json({"type": "asr.ended", "track": self.track})
        await self.cleanup()

    def _should_suppress_upstream_error(self, code: int) -> bool:
        # Inactive tracks (asr.start but no browser PCM) hit packet-timeout on hangup;
        # suppress UI toast — see volc-asr-fix-handoff §2.4 / §7.
        return code == UPSTREAM_CODE_PACKET_TIMEOUT and not self.has_received_pcm

    async def _emit_response(self, response: VolcAsrResponse) -> bool:
        if response.code != 0:
            if self._should_suppress_upstream_error(response.code):
                logger.debug(
                    "suppressed upstream error track=%s upstream_code=%s had_browser_pcm=%s",
                    self.track,
                    response.code,
                    self.has_received_pcm,
                )
                return response.is_last_package
            await self.send_error(
                code="upstream_error",
                message=f"上游错误 code={response.code}",
            )
            return True

        for event in extract_transcript_events(response.payload_msg, track=self.track):
            await self.send_json(event)
        return response.is_last_package

    async def _poll_upstream(self, *, timeout: float, wait_last: bool = False) -> bool:
        upstream = self.upstream
        if upstream is None:
            return False

        deadline = time.monotonic() + timeout
        ended = False
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                response = await asyncio.wait_for(
                    upstream.recv_response(),
                    timeout=remaining if wait_last else min(remaining, 0.05),
                )
            except asyncio.TimeoutError:
                if wait_last:
                    continue
                break
            except Exception as exc:
                logger.warning(
                    "upstream recv failed track=%s error_type=%s message=%s",
                    self.track,
                    type(exc).__name__,
                    exc,
                )
                await self.send_error(code="upstream_recv_failed", message="接收识别结果失败")
                return True

            if response is None:
                if wait_last:
                    continue
                break

            if await self._emit_response(response):
                ended = True
                break

        return ended

    async def cleanup(self) -> None:
        if self.closed:
            return
        self.closed = True
        if self.upstream is not None:
            await self.upstream.close()
            self.upstream = None


@dataclass
class AsrSessionManager:
    """Process-local ASR sessions keyed by (user_id, track)."""

    _sessions: dict[SessionKey, AsrTrackSession] = field(default_factory=dict)
    _binary_track: dict[str, AsrTrack] = field(default_factory=dict)
    client_factory: Any = field(default=default_volc_asr_client_factory)

    def reset(self) -> None:
        self._sessions.clear()
        self._binary_track.clear()

    def _session_key(self, user_id: str, track: AsrTrack) -> SessionKey:
        return user_id, track

    async def close_track(self, user_id: str, track: AsrTrack) -> None:
        key = self._session_key(user_id, track)
        session = self._sessions.pop(key, None)
        if session is not None:
            await session.cleanup()

    async def close_user(self, user_id: str) -> None:
        keys = [key for key in self._sessions if key[0] == user_id]
        for key in keys:
            session = self._sessions.pop(key, None)
            if session is not None:
                await session.cleanup()

    async def handle_start(
        self,
        user_id: str,
        websocket: WebSocket,
        message: dict[str, Any],
        *,
        settings: Settings | None = None,
    ) -> None:
        track = message.get("track")
        if track not in ("local", "remote"):
            await websocket.send_json(
                {
                    "type": "asr.error",
                    "code": "invalid_track",
                    "message": "track 必须为 local 或 remote",
                }
            )
            return

        active_settings = settings or get_settings()
        await self.close_track(user_id, track)

        session = AsrTrackSession(
            user_id=user_id,
            track=track,
            websocket=websocket,
            settings=active_settings,
            client_factory=self.client_factory,
        )
        self._sessions[self._session_key(user_id, track)] = session
        self._binary_track[user_id] = track
        await session.start(message)
        if session.upstream is None:
            self._sessions.pop(self._session_key(user_id, track), None)

    async def handle_audio(self, user_id: str, pcm: bytes, *, track: AsrTrack | None = None) -> None:
        resolved_track = track or self._binary_track.get(user_id)
        if resolved_track is None:
            return
        session = self._sessions.get(self._session_key(user_id, resolved_track))
        if session is not None:
            await session.append_audio(pcm)

    def set_binary_track(self, user_id: str, track: AsrTrack) -> None:
        if track in ("local", "remote"):
            self._binary_track[user_id] = track

    async def handle_stop(self, user_id: str, message: dict[str, Any]) -> None:
        track = message.get("track")
        if track in ("local", "remote"):
            session = self._sessions.pop(self._session_key(user_id, track), None)
            if session is not None:
                await session.stop()
            return
        for key in [key for key in self._sessions if key[0] == user_id]:
            session = self._sessions.pop(key, None)
            if session is not None:
                await session.stop()

    async def unregister(self, user_id: str) -> None:
        self._binary_track.pop(user_id, None)
        await self.close_user(user_id)


asr_session_manager = AsrSessionManager()
