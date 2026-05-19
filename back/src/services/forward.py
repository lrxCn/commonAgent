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


async def forward_chat_to_agent(
    payload: dict[str, Any],
    *,
    settings: Settings | None = None,
) -> Response | StreamingResponse:
    """POST payload to Agent; stream SSE or return JSON body unchanged."""
    resolved = settings or get_settings()
    url = _agent_chat_url(resolved)
    timeout = httpx.Timeout(resolved.AGENT_TIMEOUT_SECONDS)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            request = client.build_request(
                "POST",
                url,
                json=payload,
                headers=_agent_headers(resolved),
            )
            response = await client.send(request, stream=True)
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail={"error": "agent_unreachable", "message": str(exc)},
        ) from exc

    if response.status_code >= 400:
        body = await response.aread()
        await response.aclose()
        raise HTTPException(status_code=response.status_code, detail=body.decode("utf-8", "replace"))

    content_type = response.headers.get("content-type", "application/octet-stream")

    if "text/event-stream" in content_type:

        async def stream_body() -> AsyncIterator[bytes]:
            try:
                async for chunk in response.aiter_bytes():
                    yield chunk
            finally:
                await response.aclose()

        return StreamingResponse(
            stream_body(),
            media_type="text/event-stream",
            status_code=response.status_code,
        )

    data = await response.aread()
    await response.aclose()
    return Response(content=data, media_type=content_type, status_code=response.status_code)
