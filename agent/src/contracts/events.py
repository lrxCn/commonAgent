"""Typed observability event contracts shared by runtime and adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ObservabilityEventType(str, Enum):
    """Stable event names emitted by business code."""

    TURN_CLASSIFIED = "turn.classified"
    REWRITE_COMPLETED = "rewrite.completed"
    REWRITE_SKIPPED = "rewrite.skipped"
    RAG_ROUTED = "rag.routed"
    RAG_RETRIEVED = "rag.retrieved"
    EXECUTOR_CHOSEN = "executor.chosen"
    CONTEXT_BUDGET_COMPUTED = "context_budget.computed"
    CLIENT_ACTIONS_PARSED = "client_actions.parsed"
    GUARDRAIL_CHECKED = "guardrail.checked"
    POST_TURN_SCHEDULED = "post_turn.scheduled"
    LLM_CALL_COMPLETED = "llm_call.completed"
    PATH_METRICS_FINALIZED = "path_metrics.finalized"
    METADATA_ATTACHED = "metadata.attached"


@dataclass(frozen=True)
class ObservabilityEvent:
    """Small immutable domain event envelope."""

    name: str | ObservabilityEventType
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        normalized_name = (
            self.name.value if isinstance(self.name, ObservabilityEventType) else self.name
        )
        object.__setattr__(self, "name", normalized_name)
