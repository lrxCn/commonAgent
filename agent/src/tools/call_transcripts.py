"""Read-only call transcript tools backed by Back internal APIs."""

from __future__ import annotations

import json
from contextvars import ContextVar, Token
from typing import Any

import httpx
from langchain_core.tools import tool

from settings.config import Settings, get_settings

_current_tool_user_id: ContextVar[str | None] = ContextVar(
    "current_call_transcript_tool_user_id",
    default=None,
)


def set_call_transcript_tool_user_id(user_id: str | None) -> Token[str | None]:
    return _current_tool_user_id.set(user_id)


def reset_call_transcript_tool_user_id(token: Token[str | None]) -> None:
    _current_tool_user_id.reset(token)


def _headers(settings: Settings) -> dict[str, str]:
    headers: dict[str, str] = {}
    if settings.INTERNAL_API_KEY:
        headers["X-Internal-Key"] = settings.INTERNAL_API_KEY
    return headers


def _current_user_id() -> str:
    user_id = _current_tool_user_id.get()
    if not user_id:
        raise RuntimeError("Call transcript tools require request context user_id")
    return user_id


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


@tool
def list_call_transcripts(
    peer_user_id: str | None = None,
    since: str | None = None,
    until: str | None = None,
    limit: int = 5,
) -> str:
    """List the current user's call records by date window or peer.

    Use this first when the user asks about calls on a date, calls with a person,
    recent calls, summaries, or sensitive keyword hits. Dates should be ISO strings.
    The current user_id is injected by the runtime and must not be requested from users.
    """
    settings = get_settings()
    params: dict[str, object] = {
        "user_id": _current_user_id(),
        "limit": min(max(int(limit or 5), 1), 20),
    }
    if peer_user_id:
        params["peer_user_id"] = peer_user_id
    if since:
        params["since"] = since
    if until:
        params["until"] = until
    try:
        with httpx.Client(timeout=settings.BACK_INTERNAL_TIMEOUT_SECONDS) as client:
            response = client.get(
                f"{settings.BACK_URL.rstrip('/')}/internal/calls/transcripts",
                params=params,
                headers=_headers(settings),
            )
            response.raise_for_status()
            return _json(response.json())
    except httpx.HTTPStatusError as exc:
        return _json(
            {
                "error": "call_transcripts_unavailable",
                "status_code": exc.response.status_code,
                "message": exc.response.text[:500],
            }
        )
    except httpx.HTTPError as exc:
        return _json({"error": "call_transcripts_unavailable", "message": str(exc)})


@tool
def get_call_transcript(call_id: str) -> str:
    """Get one full call transcript for the current user by call_id.

    Use after list_call_transcripts when a specific call_id is needed. The result
    includes summary, sensitive_hits, and role-labeled transcript lines.
    """
    settings = get_settings()
    try:
        with httpx.Client(timeout=settings.BACK_INTERNAL_TIMEOUT_SECONDS) as client:
            response = client.get(
                f"{settings.BACK_URL.rstrip('/')}/internal/calls/transcripts/{call_id}",
                params={"user_id": _current_user_id()},
                headers=_headers(settings),
            )
            response.raise_for_status()
            return _json(response.json())
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return _json({"error": "not_found", "message": "没有找到这条通话记录"})
        return _json(
            {
                "error": "call_transcript_unavailable",
                "status_code": exc.response.status_code,
                "message": exc.response.text[:500],
            }
        )
    except httpx.HTTPError as exc:
        return _json({"error": "call_transcript_unavailable", "message": str(exc)})


CALL_TRANSCRIPT_TOOLS = [list_call_transcripts, get_call_transcript]
