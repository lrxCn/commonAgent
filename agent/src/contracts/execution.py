"""Executor selection contracts shared by graph and observability code."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal


class ExecutorType(str, Enum):
    """Runtime executor names recorded in trace metadata."""

    TEMPLATE = "template_executor"
    SMALL_CHAT = "small_chat_executor"
    RAG_ANSWER = "rag_answer_executor"
    ACTION = "action_executor"
    DEEPAGENTS = "deepagents_executor"


ExecutorReason = Literal[
    "turn_type_fact_update",
    "turn_type_chitchat",
    "simple_client_action",
    "complex_knowledge_task",
    "ambiguous_with_tools",
    "complex_task_rule",
    "default_deepagents",
]


@dataclass(frozen=True)
class ExecutorDecision:
    """Chosen executor and stable reason code."""

    executor: ExecutorType
    reason: ExecutorReason | str
