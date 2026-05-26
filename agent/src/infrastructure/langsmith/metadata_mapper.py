"""Map domain observability events to LangSmith-compatible metadata."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from contracts.events import ObservabilityEvent, ObservabilityEventType
from observability.path_contract import path_metrics_metadata


def event_to_metadata(event: ObservabilityEvent) -> dict[str, Any]:
    """Return the legacy trace metadata represented by one event."""
    payload = dict(event.metadata)
    name = event.name

    if name == ObservabilityEventType.TURN_CLASSIFIED.value:
        return {
            "turn_type": payload.get("turn_type", ""),
            "turn_type_reason": payload.get("turn_type_reason", ""),
        }

    if name == ObservabilityEventType.INTENT_CLASSIFIED.value:
        return payload

    if name == ObservabilityEventType.INTENT_CONFLICT_DETECTED.value:
        return payload

    if name == ObservabilityEventType.POLICY_EVALUATED.value:
        return payload

    if name == ObservabilityEventType.FALLBACK_TRIGGERED.value:
        return payload

    if name == ObservabilityEventType.REWRITE_SKIPPED.value:
        return {
            "rewrite_skipped": True,
            "rewrite_skip_reason": payload.get("rewrite_skip_reason", ""),
            "rewrite.fallback": bool(payload.get("rewrite.fallback", False)),
        }

    if name == ObservabilityEventType.REWRITE_COMPLETED.value:
        return payload

    if name == ObservabilityEventType.RAG_ROUTED.value:
        return payload

    if name == ObservabilityEventType.RAG_RETRIEVED.value:
        return payload

    if name == ObservabilityEventType.EXECUTOR_CHOSEN.value:
        return payload

    if name == ObservabilityEventType.CONTEXT_BUDGET_COMPUTED.value:
        return payload

    if name == ObservabilityEventType.CLIENT_ACTIONS_PARSED.value:
        return payload

    if name == ObservabilityEventType.GUARDRAIL_CHECKED.value:
        return payload

    if name == ObservabilityEventType.POST_TURN_SCHEDULED.value:
        metrics = payload.get("path_metrics")
        if isinstance(metrics, Mapping):
            return path_metrics_metadata(metrics)
        return payload

    if name == ObservabilityEventType.PATH_METRICS_FINALIZED.value:
        metrics = payload.get("path_metrics")
        if isinstance(metrics, Mapping):
            return path_metrics_metadata(metrics)
        return payload

    if name == ObservabilityEventType.LLM_CALL_COMPLETED.value:
        return payload

    if name == ObservabilityEventType.MEMORY_QUERY_POLISHED.value:
        return payload

    if name == ObservabilityEventType.METADATA_ATTACHED.value:
        return payload

    return payload
