"""Unified per-turn type classification for graph routing metadata."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from gateway.schemas import ToolSpec
from rag.intent import has_knowledge_intent, is_chitchat, is_user_fact_statement
from rag.router import is_pure_client_tool_intent


class TurnType(str, Enum):
    """Coarse turn category used by later runtime routing tasks."""

    FACT_UPDATE = "fact_update"
    CHITCHAT = "chitchat"
    KNOWLEDGE_QUERY = "knowledge_query"
    CLIENT_ACTION = "client_action"
    AMBIGUOUS = "ambiguous"
    GENERAL_CHAT = "general_chat"


@dataclass(frozen=True)
class TurnTypeDecision:
    """Turn type plus a stable reason code for tracing and tests."""

    turn_type: TurnType
    reason: str


_ANAPHORA_RE = re.compile(
    r"(?:它|这个|那个|上述|刚才|继续|还有吗|后者|前者|这般|那样|如此|同上|前述|"
    r"that|this|it|those|them|continue|go on|same)",
    re.IGNORECASE,
)

_SHORT_ACK_RE = re.compile(
    r"^(?:继续|再说|展开|详细点|还有呢|然后呢|那呢|这个呢|那个呢|它呢|"
    r"continue|go on|tell me more|more)\s*[。.!！?？]*$",
    re.IGNORECASE,
)


def _text(value: str | None) -> str:
    return (value or "").strip()


def _is_ambiguous_reference(text: str) -> bool:
    if not text:
        return False
    if _SHORT_ACK_RE.match(text):
        return True
    return _ANAPHORA_RE.search(text) is not None


def classify_turn_type(
    message: str,
    *,
    rewritten_query: str | None = None,
    tools_context: Sequence[ToolSpec | dict] | None = None,
) -> TurnTypeDecision:
    """
    Classify the current user turn without changing execution behavior.

    Rules are intentionally deterministic for task 28. Later tasks can consume
    this state to gate rewrite, RAG, Supervisor, or fast paths.
    """
    text = _text(message)
    rewritten = _text(rewritten_query)
    if not text and not rewritten:
        return TurnTypeDecision(TurnType.GENERAL_CHAT, "empty")

    if is_chitchat(text, rewritten):
        return TurnTypeDecision(TurnType.CHITCHAT, "chitchat_rule")

    if is_user_fact_statement(text, rewritten):
        return TurnTypeDecision(TurnType.FACT_UPDATE, "fact_statement_rule")

    if is_pure_client_tool_intent(text, tools_context, rewritten_query=rewritten):
        return TurnTypeDecision(TurnType.CLIENT_ACTION, "client_action_rule")

    if has_knowledge_intent(text, rewritten):
        return TurnTypeDecision(TurnType.KNOWLEDGE_QUERY, "knowledge_intent_rule")

    if _is_ambiguous_reference(text) or _is_ambiguous_reference(rewritten):
        return TurnTypeDecision(TurnType.AMBIGUOUS, "anaphora_or_continuation_rule")

    return TurnTypeDecision(TurnType.GENERAL_CHAT, "default_general_chat")
