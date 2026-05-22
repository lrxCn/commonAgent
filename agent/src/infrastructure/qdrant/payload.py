"""Qdrant KB payload parsing."""

from __future__ import annotations

from typing import Any

from contracts.rag import RagChannel
from domain.rag.models import RagCandidate


def payload_text(payload: dict[str, Any]) -> str:
    for key in ("text", "content", "chunk_text"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def candidate_from_payload(
    payload: dict[str, Any],
    *,
    fallback_id: object,
    channel: RagChannel,
    score: float = 0.0,
    role_id: str | None = None,
) -> RagCandidate | None:
    if role_id is not None and str(payload.get("role_id") or "").strip() != role_id:
        return None
    doc_id = str(payload.get("doc_id") or "").strip()
    chunk_id = str(payload.get("chunk_id") or fallback_id or "").strip()
    text = payload_text(payload)
    if not doc_id or not chunk_id or not text:
        return None
    return RagCandidate(
        doc_id=doc_id,
        chunk_id=chunk_id,
        text=text,
        score=score,
        channel=channel,
    )


def hit_to_candidate(hit: Any, *, channel: RagChannel, role_id: str | None = None) -> RagCandidate | None:
    payload = hit.payload if isinstance(hit.payload, dict) else {}
    score = float(hit.score) if hit.score is not None else 0.0
    return candidate_from_payload(
        payload,
        fallback_id=getattr(hit, "id", ""),
        channel=channel,
        score=score,
        role_id=role_id,
    )


def point_to_candidate(
    point: Any,
    *,
    channel: RagChannel,
    score: float = 0.0,
    role_id: str | None = None,
) -> RagCandidate | None:
    payload = point.payload if isinstance(point.payload, dict) else {}
    return candidate_from_payload(
        payload,
        fallback_id=getattr(point, "id", ""),
        channel=channel,
        score=score,
        role_id=role_id,
    )
