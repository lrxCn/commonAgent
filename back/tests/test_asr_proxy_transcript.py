"""Unit tests for ASR transcript extraction and final-line deduplication."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from services.asr_proxy import AsrTrackSession, extract_transcript_events, final_event_key
from services.volc_asr.protocol import VolcAsrResponse
from settings.config import Settings


def test_extract_transcript_multiple_definite_utterances() -> None:
    payload = {
        "result": {
            "utterances": [
                {
                    "text": "你好。",
                    "definite": True,
                    "start_time": 0,
                    "end_time": 500,
                },
                {
                    "text": "再见。",
                    "definite": True,
                    "start_time": 600,
                    "end_time": 1200,
                },
            ],
        }
    }
    events = extract_transcript_events(payload, track="local")
    assert [e["type"] for e in events] == ["asr.final", "asr.final"]
    assert events[0]["text"] == "你好。"
    assert events[1]["text"] == "再见。"


def test_final_event_key_uses_track_and_times() -> None:
    event = {
        "track": "remote",
        "text": "你好。",
        "start_time": 100,
        "end_time": 200,
    }
    assert final_event_key(event) == "remote:100:200:你好。"


class _CollectWs:
    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []

    async def send_json(self, payload: dict[str, Any]) -> None:
        self.messages.append(payload)


def test_emit_response_dedupes_repeated_finals() -> None:
    """Volcengine resends full utterance history on every audio response."""

    async def run() -> list[dict[str, Any]]:
        ws = _CollectWs()
        settings = Settings(DATABASE_URL="sqlite+pysqlite:///:memory:")
        session = AsrTrackSession(
            user_id="u1",
            track="local",
            websocket=ws,
            settings=settings,
        )
        response = VolcAsrResponse(
            code=0,
            payload_msg={
                "result": {
                    "utterances": [
                        {
                            "text": "你好。",
                            "definite": True,
                            "start_time": 0,
                            "end_time": 500,
                        }
                    ],
                }
            },
        )
        await session._emit_response(response)
        await session._emit_response(response)
        return ws.messages

    messages = asyncio.run(run())
    finals = [m for m in messages if m.get("type") == "asr.final"]
    assert len(finals) == 1
    assert finals[0]["text"] == "你好。"
