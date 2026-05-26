"""Build per-turn Agent request context (session user + role tool whitelist)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from settings.config import Settings, get_settings


def load_role_tools(tools_path: Path) -> list[dict[str, Any]]:
    """Load tool definitions from JSON; expects ``{"tools": [...]}``."""
    raw = json.loads(tools_path.read_text(encoding="utf-8"))
    tools = raw.get("tools")
    if not isinstance(tools, list):
        msg = f"Invalid tools file (missing 'tools' array): {tools_path}"
        raise ValueError(msg)
    return [tool for tool in tools if isinstance(tool, dict)]


def _tool_for_agent(tool: dict[str, Any]) -> dict[str, Any]:
    """Strip Back-only metadata before forwarding to Agent."""
    return {key: value for key, value in tool.items() if key != "roles"}


def filter_tools_for_role_ids(
    tools: list[dict[str, Any]],
    role_ids: list[str],
) -> list[dict[str, Any]]:
    """Return tools allowed for any of ``role_ids`` (union, deduped by name)."""
    allowed_roles = set(role_ids)
    seen_names: set[str] = set()
    filtered: list[dict[str, Any]] = []
    for tool in tools:
        name = tool.get("name")
        if not isinstance(name, str) or not name or name in seen_names:
            continue
        tool_roles = tool.get("roles")
        if tool_roles is not None:
            if not isinstance(tool_roles, list):
                continue
            if not any(role in allowed_roles for role in tool_roles):
                continue
        seen_names.add(name)
        filtered.append(_tool_for_agent(tool))
    return filtered


def filter_tools_for_role(tools: list[dict[str, Any]], *, role_id: str) -> list[dict[str, Any]]:
    """Deprecated: filter by a single role id."""
    return filter_tools_for_role_ids(tools, [role_id])


def build_request_context(
    *,
    user_id: str | None = None,
    role_ids: list[str] | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Assemble ``context`` for Agent ``POST /internal/chat``."""
    resolved = settings or get_settings()
    resolved_user_id = user_id if user_id is not None else resolved.DEMO_USER_ID
    resolved_role_ids = (
        list(role_ids)
        if role_ids is not None
        else [resolved.DEMO_ROLE_ID]
    )
    tools_path = resolved.resolve_tools_path()
    all_tools = load_role_tools(tools_path)
    allowed = filter_tools_for_role_ids(all_tools, resolved_role_ids)
    context: dict[str, Any] = {
        "user_id": resolved_user_id,
        "role_ids": resolved_role_ids,
        "tools": allowed,
    }
    if resolved_role_ids:
        context["role_id"] = resolved_role_ids[0]
    return context


def build_agent_chat_payload(
    *,
    thread_id: str,
    message: str,
    user_id: str | None = None,
    role_ids: list[str] | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Full body forwarded to Agent Gateway."""
    return {
        "thread_id": thread_id,
        "message": message,
        "context": build_request_context(
            user_id=user_id,
            role_ids=role_ids,
            settings=settings,
        ),
    }
