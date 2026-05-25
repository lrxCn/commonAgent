"""Passive path contract metrics for one graph turn."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from contracts.fallback import FallbackDecision
from contracts.path import COMPONENTS, LLM_COMPONENTS, PathComponent, PathMetrics


def _to_legacy(metrics: PathMetrics) -> dict[str, Any]:
    return metrics.to_legacy_dict()


def new_path_metrics(
    *,
    turn_type: str = "",
    turn_type_reason: str = "",
    fast_path: bool = False,
) -> dict[str, Any]:
    """Create the baseline metrics shape carried through a single invoke."""
    return _to_legacy(
        PathMetrics(
            turn_type=turn_type,
            turn_type_reason=turn_type_reason,
            fast_path=fast_path,
        )
    )


def ensure_path_metrics(metrics: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return a complete mutable metrics dict without mutating the input."""
    if not metrics:
        return new_path_metrics()

    merged = new_path_metrics(
        turn_type=str(metrics.get("turn_type") or ""),
        turn_type_reason=str(metrics.get("turn_type_reason") or ""),
        fast_path=bool(metrics.get("fast_path", False)),
    )
    for key, value in deepcopy(dict(metrics)).items():
        if key in COMPONENTS and isinstance(value, Mapping):
            merged[key] = {**merged[key], **dict(value)}
        else:
            merged[key] = value
    return merged


def update_path_component(
    metrics: Mapping[str, Any] | None,
    component: PathComponent,
    *,
    should_call: bool | None = None,
    called: bool | None = None,
) -> dict[str, Any]:
    """Update one component's should/called flags."""
    updated = ensure_path_metrics(metrics)
    component_metrics = dict(updated.get(component) or {})
    if should_call is not None:
        component_metrics["should_call"] = bool(should_call)
    if called is not None:
        component_metrics["called"] = bool(called)
    updated[component] = component_metrics
    return updated


def mark_fast_path(
    metrics: Mapping[str, Any] | None,
    *,
    enabled: bool = True,
) -> dict[str, Any]:
    """Mark whether this turn used a graph fast path."""
    updated = ensure_path_metrics(metrics)
    updated["fast_path"] = bool(enabled)
    return updated


def mark_post_turn_schedule(
    metrics: Mapping[str, Any] | None,
    *,
    scheduled: bool,
    error: str = "",
) -> dict[str, Any]:
    """Record whether post-turn background work was scheduled."""
    updated = ensure_path_metrics(metrics)
    updated["post_turn_scheduled"] = bool(scheduled)
    updated["post_turn_schedule_error"] = str(error or "")
    return updated


def mark_memory_write_mode(
    metrics: Mapping[str, Any] | None,
    *,
    mode: str,
    attribute: str = "",
) -> dict[str, Any]:
    """Record structured vs inferred mem0 write mode for path contract traces."""
    updated = ensure_path_metrics(metrics)
    updated["memory_write_mode"] = str(mode)
    if attribute.strip():
        updated["memory_write_record_attribute"] = attribute.strip()
    return updated


def increment_fallback_count(
    metrics: Mapping[str, Any] | None,
    count: int = 1,
) -> dict[str, Any]:
    """Record fallback events that the graph can observe directly."""
    updated = ensure_path_metrics(metrics)
    updated["fallback_count"] = int(updated.get("fallback_count") or 0) + count
    return updated


def record_fallback_decision(
    metrics: Mapping[str, Any] | None,
    decision: FallbackDecision,
) -> dict[str, Any]:
    """Record the latest normalized fallback decision in path metrics."""
    updated = ensure_path_metrics(metrics)
    if decision.triggered:
        updated["fallback_count"] = int(updated.get("fallback_count") or 0) + 1
    updated["fallback_triggered"] = bool(decision.triggered)
    updated["fallback_layer"] = str(decision.layer)
    updated["fallback_reason"] = decision.reason
    updated["fallback_action"] = str(decision.action)
    updated["fallback_user_visible"] = bool(decision.user_visible)
    updated["fallback_recovered"] = bool(decision.recovered)
    updated["fallback_original_route"] = decision.original_route
    updated["fallback_final_route"] = decision.final_route
    return updated


def finalize_path_metrics(metrics: Mapping[str, Any] | None) -> dict[str, Any]:
    """Compute derived counts and pass/fail status."""
    finalized = ensure_path_metrics(metrics)
    llm_call_count = 0
    failures: list[str] = []

    for component in COMPONENTS:
        component_metrics = finalized.get(component) or {}
        should_call = bool(component_metrics.get("should_call"))
        called = bool(component_metrics.get("called"))
        if component in LLM_COMPONENTS and called:
            llm_call_count += 1
        if called and not should_call:
            failures.append(f"{component}.called_without_should")

    finalized["llm_call_count"] = llm_call_count
    if failures:
        finalized["path_contract"] = "fail"
        finalized["path_contract_reason"] = ",".join(failures)
    else:
        finalized["path_contract"] = "pass"
        finalized["path_contract_reason"] = "ok"
    return finalized


def path_metrics_metadata(metrics: Mapping[str, Any] | None) -> dict[str, Any]:
    """Flatten path metrics for trace metadata."""
    finalized = finalize_path_metrics(metrics)
    metadata: dict[str, Any] = {
        "path_metrics": finalized,
        "path_contract": finalized["path_contract"],
        "path_contract_reason": finalized["path_contract_reason"],
        "llm_call_count": finalized["llm_call_count"],
        "fallback_count": finalized.get("fallback_count", 0),
        "fallback.triggered": bool(finalized.get("fallback_triggered", False)),
        "fallback.layer": finalized.get("fallback_layer", ""),
        "fallback.reason": finalized.get("fallback_reason", ""),
        "fallback.action": finalized.get("fallback_action", ""),
        "fallback.user_visible": bool(finalized.get("fallback_user_visible", False)),
        "fallback.recovered": bool(finalized.get("fallback_recovered", False)),
        "fallback.original_route": finalized.get("fallback_original_route", ""),
        "fallback.final_route": finalized.get("fallback_final_route", ""),
        "fast_path": finalized.get("fast_path", False),
        "post_turn_scheduled": finalized.get("post_turn_scheduled", False),
        "post_turn_schedule_error": finalized.get("post_turn_schedule_error", ""),
        "memory_write.mode": finalized.get("memory_write_mode", ""),
        "memory_write.record.attribute": finalized.get("memory_write_record_attribute", ""),
    }
    for component in COMPONENTS:
        values = finalized.get(component) or {}
        metadata[f"{component}.should_call"] = bool(values.get("should_call"))
        metadata[f"{component}.called"] = bool(values.get("called"))
    return metadata
