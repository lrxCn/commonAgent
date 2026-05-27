"""SAUC binary frame encoding/decoding (aligned with back/demo/sauc_python)."""

from __future__ import annotations

import gzip
import json
import struct
from dataclasses import dataclass
from typing import Any

PROTOCOL_VERSION = 0b0001

CLIENT_FULL_REQUEST = 0b0001
CLIENT_AUDIO_ONLY_REQUEST = 0b0010
SERVER_FULL_RESPONSE = 0b1001
SERVER_ERROR_RESPONSE = 0b1111

FLAG_NO_SEQUENCE = 0b0000
FLAG_POS_SEQUENCE = 0b0001
FLAG_NEG_SEQUENCE = 0b0010
FLAG_NEG_WITH_SEQUENCE = 0b0011

SERIALIZATION_JSON = 0b0001
COMPRESSION_GZIP = 0b0001

DEFAULT_SAMPLE_RATE = 16_000
DEFAULT_BITS = 16
DEFAULT_CHANNELS = 1


@dataclass
class VolcAsrResponse:
    code: int = 0
    event: int = 0
    is_last_package: bool = False
    payload_sequence: int = 0
    payload_size: int = 0
    payload_msg: dict[str, Any] | None = None


def gzip_compress(data: bytes) -> bytes:
    return gzip.compress(data)


def gzip_decompress(data: bytes) -> bytes:
    return gzip.decompress(data)


def _header_bytes(
    *,
    message_type: int,
    message_flags: int,
    serialization: int = SERIALIZATION_JSON,
    compression: int = COMPRESSION_GZIP,
) -> bytes:
    header = bytearray()
    header.append((PROTOCOL_VERSION << 4) | 1)
    header.append((message_type << 4) | message_flags)
    header.append((serialization << 4) | compression)
    header.extend(b"\x00")
    return bytes(header)


def build_full_client_payload(user_id: str) -> dict[str, Any]:
    return {
        "user": {"uid": user_id},
        "audio": {
            "format": "wav",
            "codec": "raw",
            "rate": DEFAULT_SAMPLE_RATE,
            "bits": DEFAULT_BITS,
            "channel": DEFAULT_CHANNELS,
        },
        "request": {
            "model_name": "bigmodel",
            "enable_itn": True,
            "enable_punc": True,
            "enable_ddc": True,
            "show_utterances": True,
            "enable_nonstream": False,
        },
    }


def build_full_client_request(seq: int, user_id: str) -> bytes:
    payload_bytes = json.dumps(build_full_client_payload(user_id)).encode("utf-8")
    compressed = gzip_compress(payload_bytes)
    request = bytearray()
    request.extend(
        _header_bytes(
            message_type=CLIENT_FULL_REQUEST,
            message_flags=FLAG_POS_SEQUENCE,
        )
    )
    request.extend(struct.pack(">i", seq))
    request.extend(struct.pack(">I", len(compressed)))
    request.extend(compressed)
    return bytes(request)


def build_audio_only_request(seq: int, segment: bytes, *, is_last: bool = False) -> bytes:
    send_seq = -seq if is_last else seq
    flags = FLAG_NEG_WITH_SEQUENCE if is_last else FLAG_POS_SEQUENCE
    compressed = gzip_compress(segment)
    request = bytearray()
    request.extend(
        _header_bytes(
            message_type=CLIENT_AUDIO_ONLY_REQUEST,
            message_flags=flags,
        )
    )
    request.extend(struct.pack(">i", send_seq))
    request.extend(struct.pack(">I", len(compressed)))
    request.extend(compressed)
    return bytes(request)


def parse_response(msg: bytes) -> VolcAsrResponse:
    response = VolcAsrResponse()
    if len(msg) < 4:
        return response

    header_size = msg[0] & 0x0F
    message_type = msg[1] >> 4
    message_type_specific_flags = msg[1] & 0x0F
    serialization_method = msg[2] >> 4
    message_compression = msg[2] & 0x0F

    payload = msg[header_size * 4 :]

    if message_type_specific_flags & 0x01:
        response.payload_sequence = struct.unpack(">i", payload[:4])[0]
        payload = payload[4:]
    if message_type_specific_flags & 0x02:
        response.is_last_package = True
    if message_type_specific_flags & 0x04:
        response.event = struct.unpack(">i", payload[:4])[0]
        payload = payload[4:]

    if message_type == SERVER_FULL_RESPONSE:
        response.payload_size = struct.unpack(">I", payload[:4])[0]
        payload = payload[4:]
    elif message_type == SERVER_ERROR_RESPONSE:
        response.code = struct.unpack(">i", payload[:4])[0]
        response.payload_size = struct.unpack(">I", payload[4:8])[0]
        payload = payload[8:]

    if not payload:
        return response

    if message_compression == COMPRESSION_GZIP:
        try:
            payload = gzip_decompress(payload)
        except OSError:
            return response

    if serialization_method == SERIALIZATION_JSON:
        try:
            parsed = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return response
        if isinstance(parsed, dict):
            response.payload_msg = parsed

    return response


def pcm_segment_size_bytes(*, segment_ms: int, sample_rate: int = DEFAULT_SAMPLE_RATE) -> int:
    bytes_per_second = sample_rate * 2 * DEFAULT_CHANNELS
    return max(1, bytes_per_second * segment_ms // 1000)
