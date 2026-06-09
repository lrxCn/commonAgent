"""Call transcript persistence and internal query routes."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy.orm import Session

from api.deps import get_db_session, require_current_user, require_internal_key
from api.errors import bad_request, not_found
from db.models import User
from services.call_transcripts import (
    get_call_transcript,
    list_call_transcripts,
    transcript_detail,
    transcript_list_item,
    upsert_call_transcript,
)
from settings.config import Settings, get_settings

router = APIRouter(prefix="/api/calls", tags=["call-transcripts"])
internal_router = APIRouter(
    prefix="/internal/calls",
    tags=["internal-call-transcripts"],
    dependencies=[Depends(require_internal_key)],
)


class TranscriptLine(BaseModel):
    track: Literal["local", "remote"]
    role_label: str = Field(min_length=1, max_length=128)
    text: str = Field(min_length=1, max_length=4000)
    seq: int = Field(ge=1)
    start_time: float | None = None
    end_time: float | None = None


class CallTranscriptUpsertBody(BaseModel):
    call_id: str | None = Field(default=None, min_length=1, max_length=128)
    peer_user_id: str = Field(min_length=1, max_length=64)
    peer_display_name: str = Field(min_length=1, max_length=128)
    started_at: datetime
    ended_at: datetime
    duration_ms: int = Field(ge=0)
    lines: list[TranscriptLine] = Field(min_length=1)

    @field_validator("peer_user_id", "peer_display_name", mode="before")
    @classmethod
    def _strip_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @model_validator(mode="after")
    def _validate_time_range(self) -> "CallTranscriptUpsertBody":
        if self.ended_at < self.started_at:
            raise ValueError("ended_at must be greater than or equal to started_at")
        return self


class CallTranscriptPersistResponse(BaseModel):
    id: str
    call_id: str


@router.post("/{call_id}/transcript", response_model=CallTranscriptPersistResponse)
def post_call_transcript(
    call_id: str,
    body: CallTranscriptUpsertBody,
    user: Annotated[User, Depends(require_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    if body.call_id is not None and body.call_id != call_id:
        raise bad_request("body.call_id 与路径 call_id 不一致")
    if body.peer_user_id == user.user_id:
        raise bad_request("peer_user_id 不能等于当前用户")

    result = upsert_call_transcript(
        db,
        call_id=call_id,
        user_id=user.user_id,
        peer_user_id=body.peer_user_id,
        peer_display_name=body.peer_display_name,
        started_at=body.started_at,
        ended_at=body.ended_at,
        duration_ms=body.duration_ms,
        lines=[line.model_dump(exclude_none=True) for line in body.lines],
        sensitive_words=settings.call_transcript_sensitive_words(),
    )
    return CallTranscriptPersistResponse(
        id=result.transcript.id,
        call_id=result.transcript.call_id,
    )


@internal_router.get("/transcripts")
def internal_list_call_transcripts(
    db: Annotated[Session, Depends(get_db_session)],
    user_id: Annotated[str, Query(min_length=1, max_length=64)],
    peer_user_id: Annotated[str | None, Query(max_length=64)] = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = 5,
) -> dict[str, object]:
    items = list_call_transcripts(
        db,
        user_id=user_id,
        peer_user_id=peer_user_id,
        since=since,
        until=until,
        limit=limit,
    )
    return {"items": [transcript_list_item(item) for item in items]}


@internal_router.get("/transcripts/{call_id}")
def internal_get_call_transcript(
    call_id: str,
    db: Annotated[Session, Depends(get_db_session)],
    user_id: Annotated[str, Query(min_length=1, max_length=64)],
) -> dict[str, object]:
    transcript = get_call_transcript(db, user_id=user_id, call_id=call_id)
    if transcript is None:
        raise not_found("通话记录不存在")
    return transcript_detail(transcript)
