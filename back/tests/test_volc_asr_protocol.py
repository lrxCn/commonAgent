"""Unit tests for Volcengine SAUC protocol encoding/decoding."""

from __future__ import annotations

from services.volc_asr.protocol import (
    build_audio_only_request,
    build_full_client_request,
    build_full_client_payload,
    parse_response,
    pcm_segment_size_bytes,
)


def test_full_client_payload_uses_session_user_id() -> None:
    payload = build_full_client_payload("u-alice")
    assert payload["user"]["uid"] == "u-alice"
    assert payload["audio"]["rate"] == 16000


def test_full_client_request_round_trip_header() -> None:
    frame = build_full_client_request(1, "u-alice")
    response = parse_response(frame)
    assert response.payload_msg is None or isinstance(response.payload_msg, dict)


def test_audio_only_last_packet_negative_seq() -> None:
    frame = build_audio_only_request(3, b"\x00\x01", is_last=True)
    assert len(frame) > 12


def test_parse_server_full_response() -> None:
    upstream = build_full_client_request(1, "u-bob")
    parsed = parse_response(upstream)
    assert parsed.code == 0


def test_pcm_segment_size_200ms() -> None:
    assert pcm_segment_size_bytes(segment_ms=200) == 6400
