"""Routing contracts shared by graph nodes, tracing, and tests."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal


class TurnType(str, Enum):
    """Coarse turn category for one user turn."""

    FACT_UPDATE = "fact_update"
    MEMORY_QUERY = "memory_query"
    CHITCHAT = "chitchat"
    KNOWLEDGE_QUERY = "knowledge_query"
    CLIENT_ACTION = "client_action"
    AMBIGUOUS = "ambiguous"
    GENERAL_CHAT = "general_chat"
    SAFETY_REFUSAL = "safety_refusal"


TurnReason = Literal[
    "empty",
    "chitchat_rule",
    "fact_statement_rule",
    "client_action_rule",
    "knowledge_intent_rule",
    "anaphora_or_continuation_rule",
    "default_general_chat",
]


@dataclass(frozen=True)
class TurnTypeDecision:
    """Turn type plus a stable reason code for tracing and tests."""

    turn_type: TurnType
    reason: TurnReason | str
