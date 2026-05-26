"""Forward chat requests to the internal Agent Gateway."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx
from fastapi import HTTPException
from fastapi.responses import Response, StreamingResponse

from settings.config import Settings, get_settings


def _agent_headers(settings: Settings) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if settings.INTERNAL_API_KEY:
        headers["X-Internal-Key"] = settings.INTERNAL_API_KEY
    return headers


def _agent_chat_url(settings: Settings) -> str:
    base = settings.AGENT_URL.rstrip("/")
    return f"{base}/internal/chat"


def _agent_thread_messages_url(settings: Settings, thread_id: str) -> str:
    base = settings.AGENT_URL.rstrip("/")
    return f"{base}/internal/threads/{thread_id}/messages"


async def _close_agent_response(
    response: httpx.Response,
    client: httpx.AsyncClient,
) -> None:
    await response.aclose()
    await client.aclose()


async def forward_chat_to_agent(
    payload: dict[str, Any],
    *,
    settings: Settings | None = None,
) -> Response | StreamingResponse:
    """POST payload to Agent; stream SSE or return JSON body unchanged."""
    resolved = settings or get_settings()
    url = _agent_chat_url(resolved)
    timeout = httpx.Timeout(resolved.AGENT_TIMEOUT_SECONDS)
    client = httpx.AsyncClient(timeout=timeout)

    try:
        request = client.build_request(
            "POST",
            url,
            json=payload,
            headers=_agent_headers(resolved),
        )
        response = await client.send(request, stream=True)
    except httpx.RequestError as exc:
        await client.aclose()
        raise HTTPException(
            status_code=502,
            detail={"error": "agent_unreachable", "message": str(exc)},
        ) from exc

    if response.status_code >= 400:
        body = await response.aread()
        await _close_agent_response(response, client)
        raise HTTPException(status_code=response.status_code, detail=body.decode("utf-8", "replace"))

    content_type = response.headers.get("content-type", "application/octet-stream")

    if "text/event-stream" in content_type:

        async def stream_body() -> AsyncIterator[bytes]:
            try:
                async for chunk in response.aiter_bytes():
                    yield chunk
            except httpx.ReadError:
                # Browser disconnected or Agent closed the stream early.
                return
            finally:
                await _close_agent_response(response, client)

        return StreamingResponse(
            stream_body(),
            media_type="text/event-stream",
            status_code=response.status_code,
        )

    try:
        data = await response.aread()
    finally:
        await _close_agent_response(response, client)
    return Response(content=data, media_type=content_type, status_code=response.status_code)


async def forward_thread_history_to_agent(
    thread_id: str,
    *,
    cursor: str | None = None,
    limit: int | None = None,
    settings: Settings | None = None,
) -> Response:
    """GET paginated checkpoint history from Agent."""
    resolved = settings or get_settings()
    url = _agent_thread_messages_url(resolved, thread_id)
    params: dict[str, str | int] = {}
    if cursor is not None:
        params["cursor"] = cursor
    if limit is not None:
        params["limit"] = limit
    timeout = httpx.Timeout(resolved.AGENT_TIMEOUT_SECONDS)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(
                url,
                params=params or None,
                headers=_agent_headers(resolved),
            )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail={"error": "agent_unreachable", "message": str(exc)},
        ) from exc

    if response.status_code >= 400:
        raise HTTPException(
            status_code=response.status_code,
            detail=response.text,
        )

    content_type = response.headers.get("content-type", "application/json")
    return Response(content=response.content, media_type=content_type, status_code=response.status_code)
