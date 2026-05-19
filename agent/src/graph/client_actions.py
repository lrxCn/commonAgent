"""Parse and validate Supervisor LLM output for external client_actions (architecture §7)."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from gateway.schemas import ClientAction, ToolSpec
from pydantic import ValidationError

CLIENT_ACTIONS_METADATA_KEY = "client_actions"

ERROR_PARSE = "parse_error"
ERROR_TOOL_NOT_ALLOWED = "tool_not_allowed"
ERROR_VALIDATION = "validation_error"

_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*\n?(.*?)\n?```\s*$", re.DOTALL | re.IGNORECASE)


@dataclass(frozen=True)
class ClientActionsParseOutcome:
    """Result of parsing and validating LLM text for client_actions."""

    kind: Literal["text", "client_actions", "error"]
    actions: tuple[ClientAction, ...] = ()
    error_code: str | None = None
    error_message: str | None = None


def _strip_json_fences(text: str) -> str:
    stripped = text.strip()
    match = _JSON_FENCE_RE.match(stripped)
    if match:
        return match.group(1).strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return stripped


def extract_json_object(text: str) -> dict[str, Any] | None:
    """Extract a JSON object from raw LLM text (plain or fenced)."""
    candidate = _strip_json_fences(text)
    if not candidate:
        return None
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


def _tools_by_name(tools: Sequence[ToolSpec]) -> dict[str, ToolSpec]:
    return {spec.name: spec for spec in tools}


def _looks_like_client_actions_payload(text: str) -> bool:
    lowered = text.lower()
    return '"client_actions"' in lowered or "client_actions" in lowered


def parse_client_actions_payload(payload: Mapping[str, Any]) -> list[dict[str, Any]] | None:
    """Return raw action dicts from a parsed JSON object, or None if key missing/invalid."""
    raw = payload.get("client_actions")
    if raw is None:
        return None
    if not isinstance(raw, list) or not raw:
        return None
    actions: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            return None
        actions.append(item)
    return actions


def validate_client_actions(
    raw_actions: Sequence[Mapping[str, Any]],
    tools: Sequence[ToolSpec],
) -> ClientActionsParseOutcome:
    """Validate parsed actions against the per-request tool whitelist."""
    allowed = _tools_by_name(tools)
    if not allowed:
        return ClientActionsParseOutcome(
            kind="error",
            error_code=ERROR_TOOL_NOT_ALLOWED,
            error_message="No external tools are allowed for this request.",
        )

    validated: list[ClientAction] = []
    for raw in raw_actions:
        tool_name = raw.get("tool")
        if not isinstance(tool_name, str) or not tool_name.strip():
            return ClientActionsParseOutcome(
                kind="error",
                error_code=ERROR_VALIDATION,
                error_message="Each client action must include a non-empty tool name.",
            )
        name = tool_name.strip()
        if name not in allowed:
            return ClientActionsParseOutcome(
                kind="error",
                error_code=ERROR_TOOL_NOT_ALLOWED,
                error_message=f"Tool '{name}' is not in the request tool whitelist.",
            )

        spec = allowed[name]
        args = raw.get("args", {})
        if args is None:
            args = {}
        if not isinstance(args, dict):
            return ClientActionsParseOutcome(
                kind="error",
                error_code=ERROR_VALIDATION,
                error_message=f"Tool '{name}' args must be a JSON object.",
            )

        try:
            action = ClientAction(
                tool=name,
                args=args,
                requires_approval=spec.requires_approval,
            )
        except ValidationError as exc:
            return ClientActionsParseOutcome(
                kind="error",
                error_code=ERROR_VALIDATION,
                error_message=str(exc.errors()[0].get("msg", "validation failed")),
            )
        validated.append(action)

    return ClientActionsParseOutcome(kind="client_actions", actions=tuple(validated))


def parse_client_actions_from_llm(
    text: str,
    tools: Sequence[ToolSpec],
) -> ClientActionsParseOutcome:
    """Parse LLM output and validate client_actions when the payload is present."""
    stripped = text.strip()
    if not stripped:
        return ClientActionsParseOutcome(kind="text")

    payload = extract_json_object(stripped)
    if payload is None:
        if _looks_like_client_actions_payload(stripped):
            return ClientActionsParseOutcome(
                kind="error",
                error_code=ERROR_PARSE,
                error_message="Failed to parse client_actions JSON from model output.",
            )
        return ClientActionsParseOutcome(kind="text")

    raw_actions = parse_client_actions_payload(payload)
    if raw_actions is None:
        if "client_actions" in payload:
            return ClientActionsParseOutcome(
                kind="error",
                error_code=ERROR_PARSE,
                error_message="client_actions must be a non-empty JSON array.",
            )
        return ClientActionsParseOutcome(kind="text")

    return validate_client_actions(raw_actions, tools)


def client_actions_to_metadata(actions: Sequence[ClientAction]) -> list[dict[str, Any]]:
    return [action.model_dump() for action in actions]


def build_client_actions_assistant_message(actions: Sequence[ClientAction]) -> Any:
    """AIMessage with client_actions metadata for checkpoint replay (no ToolMessage)."""
    from langchain_core.messages import AIMessage

    return AIMessage(
        content="",
        additional_kwargs={CLIENT_ACTIONS_METADATA_KEY: client_actions_to_metadata(actions)},
    )


def supervisor_client_actions_instruction_block() -> str:
    """Append to supervisor instructions when external tools are available."""
    return (
        "When the user clearly wants an external client tool from the list above, "
        "respond with **only** a JSON object (no markdown fences, no extra prose):\n"
        '{"client_actions": [{"tool": "<name>", "args": {...}}]}\n'
        "Use tool names exactly as listed. The server applies requires_approval from the tool spec. "
        "Do not claim you executed the tool."
    )
