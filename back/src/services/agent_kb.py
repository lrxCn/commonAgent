"""HTTP client for Agent internal KB APIs."""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import HTTPException

from settings.config import Settings, get_settings


def _agent_headers(settings: Settings) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if settings.INTERNAL_API_KEY:
        headers["X-Internal-Key"] = settings.INTERNAL_API_KEY
    return headers


def _agent_base(settings: Settings) -> str:
    return settings.AGENT_URL.rstrip("/")


def _raise_agent_error(response: httpx.Response) -> None:
    try:
        body = response.json()
        detail = body.get("detail", response.text)
    except ValueError:
        detail = response.text
    raise HTTPException(status_code=response.status_code, detail=detail)


def agent_kb_ingest(
    payload: dict[str, Any],
    *,
    settings: Settings | None = None,
) -> dict[str, Any]:
    resolved = settings or get_settings()
    url = f"{_agent_base(resolved)}/internal/kb/ingest"
    timeout = httpx.Timeout(resolved.AGENT_TIMEOUT_SECONDS)
    try:
        response = httpx.post(url, json=payload, headers=_agent_headers(resolved), timeout=timeout)
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail={"error": "agent_unreachable", "message": str(exc)},
        ) from exc
    if response.status_code >= 400:
        _raise_agent_error(response)
    return response.json()


def agent_kb_list_documents(
    role_ids: list[str],
    *,
    settings: Settings | None = None,
) -> dict[str, Any]:
    resolved = settings or get_settings()
    url = f"{_agent_base(resolved)}/internal/kb/documents"
    params = [("role_id", role_id) for role_id in role_ids]
    timeout = httpx.Timeout(resolved.AGENT_TIMEOUT_SECONDS)
    try:
        response = httpx.get(
            url,
            params=params,
            headers=_agent_headers(resolved),
            timeout=timeout,
        )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail={"error": "agent_unreachable", "message": str(exc)},
        ) from exc
    if response.status_code >= 400:
        _raise_agent_error(response)
    return response.json()


def agent_kb_get_document(
    doc_id: str,
    *,
    settings: Settings | None = None,
) -> dict[str, Any]:
    resolved = settings or get_settings()
    url = f"{_agent_base(resolved)}/internal/kb/documents/{doc_id}"
    timeout = httpx.Timeout(resolved.AGENT_TIMEOUT_SECONDS)
    try:
        response = httpx.get(
            url,
            headers=_agent_headers(resolved),
            timeout=timeout,
        )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail={"error": "agent_unreachable", "message": str(exc)},
        ) from exc
    if response.status_code >= 400:
        _raise_agent_error(response)
    return response.json()


def agent_kb_delete_document(
    doc_id: str,
    *,
    settings: Settings | None = None,
) -> None:
    resolved = settings or get_settings()
    url = f"{_agent_base(resolved)}/internal/kb/documents/{doc_id}"
    timeout = httpx.Timeout(resolved.AGENT_TIMEOUT_SECONDS)
    try:
        response = httpx.delete(
            url,
            headers=_agent_headers(resolved),
            timeout=timeout,
        )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail={"error": "agent_unreachable", "message": str(exc)},
        ) from exc
    if response.status_code >= 400:
        _raise_agent_error(response)
