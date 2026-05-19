"""Build per-turn Agent request context (demo user + role tool whitelist)."""

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


def filter_tools_for_role(tools: list[dict[str, Any]], *, role_id: str) -> list[dict[str, Any]]:
    """Return tools allowed for ``role_id`` (demo: pass through entire list)."""
    _ = role_id
    return list(tools)


def build_request_context(settings: Settings | None = None) -> dict[str, Any]:
    """Assemble ``context`` for Agent ``POST /internal/chat``."""
    resolved = settings or get_settings()
    tools_path = resolved.resolve_tools_path()
    all_tools = load_role_tools(tools_path)
    allowed = filter_tools_for_role(all_tools, role_id=resolved.DEMO_ROLE_ID)
    return {
        "user_id": resolved.DEMO_USER_ID,
        "role_id": resolved.DEMO_ROLE_ID,
        "tools": allowed,
    }


def build_agent_chat_payload(
    *,
    thread_id: str,
    message: str,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Full body forwarded to Agent Gateway."""
    return {
        "thread_id": thread_id,
        "message": message,
        "context": build_request_context(settings),
    }
