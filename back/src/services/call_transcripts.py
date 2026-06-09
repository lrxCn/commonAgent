"""Persistence and query helpers for call transcripts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from db.models import CallTranscript
from sqlalchemy import select
from sqlalchemy.orm import Session

MAX_SUMMARY_CHARS = 360
MAX_DETAIL_LINES = 200


@dataclass(frozen=True)
class UpsertResult:
    transcript: CallTranscript
    created: bool


def normalize_lines(lines: list[dict[str, object]]) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    for index, item in enumerate(lines, start=1):
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        track = item.get("track")
        if track not in ("local", "remote"):
            track = "local"
        role_label = str(item.get("role_label") or track).strip()
        seq = item.get("seq")
        try:
            seq_int = int(seq) if seq is not None else index
        except (TypeError, ValueError):
            seq_int = index
        line: dict[str, object] = {
            "track": track,
            "role_label": role_label,
            "text": text,
            "seq": seq_int,
        }
        for source_key, target_key in (
            ("start_time", "start_time"),
            ("end_time", "end_time"),
        ):
            value = item.get(source_key)
            if isinstance(value, (int, float)):
                line[target_key] = value
        normalized.append(line)
    return sorted(
        normalized,
        key=lambda line: (
            line.get("start_time")
            if isinstance(line.get("start_time"), (int, float))
            else 10**15,
            int(line.get("seq") or 0),
        ),
    )


def build_transcript_summary(lines: list[dict[str, object]]) -> str:
    texts = [str(line.get("text") or "").strip() for line in lines]
    joined = " ".join(text for text in texts if text)
    if not joined:
        return "本次通话没有可用转写内容。"
    if len(joined) <= MAX_SUMMARY_CHARS:
        return joined
    return f"{joined[:MAX_SUMMARY_CHARS].rstrip()}..."


def find_sensitive_hits(
    lines: list[dict[str, object]],
    sensitive_words: list[str],
) -> list[dict[str, object]]:
    hits: list[dict[str, object]] = []
    seen: set[tuple[str, int]] = set()
    for line in lines:
        text = str(line.get("text") or "")
        seq = int(line.get("seq") or 0)
        for word in sensitive_words:
            if not word or word not in text:
                continue
            key = (word, seq)
            if key in seen:
                continue
            seen.add(key)
            hits.append(
                {
                    "word": word,
                    "seq": seq,
                    "track": line.get("track"),
                    "role_label": line.get("role_label"),
                    "text": text,
                }
            )
    return hits


def upsert_call_transcript(
    db: Session,
    *,
    call_id: str,
    user_id: str,
    peer_user_id: str,
    peer_display_name: str,
    started_at: datetime,
    ended_at: datetime,
    duration_ms: int,
    lines: list[dict[str, object]],
    sensitive_words: list[str],
) -> UpsertResult:
    normalized_lines = normalize_lines(lines)
    summary = build_transcript_summary(normalized_lines)
    sensitive_hits = find_sensitive_hits(normalized_lines, sensitive_words)
    existing = db.scalar(
        select(CallTranscript).where(
            CallTranscript.user_id == user_id,
            CallTranscript.call_id == call_id,
        )
    )
    created = existing is None
    transcript = existing or CallTranscript(
        id=str(uuid4()), call_id=call_id, user_id=user_id
    )
    transcript.peer_user_id = peer_user_id
    transcript.peer_display_name = peer_display_name
    transcript.started_at = started_at
    transcript.ended_at = ended_at
    transcript.duration_ms = max(0, int(duration_ms))
    transcript.lines = normalized_lines
    transcript.summary = summary
    transcript.sensitive_hits = sensitive_hits
    if created:
        db.add(transcript)
    db.commit()
    db.refresh(transcript)
    return UpsertResult(transcript=transcript, created=created)


def list_call_transcripts(
    db: Session,
    *,
    user_id: str,
    peer_user_id: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = 5,
) -> list[CallTranscript]:
    stmt = select(CallTranscript).where(CallTranscript.user_id == user_id)
    if peer_user_id:
        stmt = stmt.where(CallTranscript.peer_user_id == peer_user_id)
    if since is not None:
        stmt = stmt.where(CallTranscript.ended_at >= since)
    if until is not None:
        stmt = stmt.where(CallTranscript.ended_at < until)
    stmt = stmt.order_by(CallTranscript.ended_at.desc()).limit(min(max(limit, 1), 20))
    return list(db.scalars(stmt).all())


def get_call_transcript(
    db: Session,
    *,
    user_id: str,
    call_id: str,
) -> CallTranscript | None:
    return db.scalar(
        select(CallTranscript).where(
            CallTranscript.user_id == user_id,
            CallTranscript.call_id == call_id,
        )
    )


def transcript_list_item(transcript: CallTranscript) -> dict[str, object]:
    lines = list(transcript.lines or [])
    sensitive_hits = list(transcript.sensitive_hits or [])
    return {
        "id": transcript.id,
        "call_id": transcript.call_id,
        "peer_user_id": transcript.peer_user_id,
        "peer_display_name": transcript.peer_display_name,
        "started_at": transcript.started_at.isoformat(),
        "ended_at": transcript.ended_at.isoformat(),
        "duration_ms": transcript.duration_ms,
        "line_count": len(lines),
        "summary": transcript.summary,
        "sensitive_hit_count": len(sensitive_hits),
        "sensitive_words": sorted(
            {str(hit.get("word")) for hit in sensitive_hits if hit.get("word")}
        ),
    }


def transcript_detail(
    transcript: CallTranscript,
    *,
    max_lines: int = MAX_DETAIL_LINES,
) -> dict[str, object]:
    lines = list(transcript.lines or [])
    truncated = len(lines) > max_lines
    return {
        **transcript_list_item(transcript),
        "sensitive_hits": list(transcript.sensitive_hits or []),
        "lines": lines[:max_lines],
        "truncated": truncated,
        "total_lines": len(lines),
    }
