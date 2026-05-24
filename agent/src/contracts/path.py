"""Typed path metrics contract with legacy dict adapters."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Literal


PathComponent = Literal["rewrite", "rag_router", "rag", "supervisor"]

COMPONENTS: tuple[PathComponent, ...] = (
    "rewrite",
    "rag_router",
    "rag",
    "supervisor",
)
LLM_COMPONENTS = frozenset({"rewrite", "rag_router", "supervisor"})


class PathContractStatus(str, Enum):
    """Path contract validation status."""

    UNKNOWN = "unknown"
    PASS = "pass"
    FAIL = "fail"


@dataclass(frozen=True)
class PathComponentMetrics:
    """Should/called flags for one pipeline component."""

    should_call: bool = False
    called: bool = False

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any] | None) -> "PathComponentMetrics":
        if not value:
            return cls()
        return cls(
            should_call=bool(value.get("should_call")),
            called=bool(value.get("called")),
        )


@dataclass(frozen=True)
class PathMetrics:
    """Complete single-turn path metrics contract."""

    turn_type: str = ""
    turn_type_reason: str = ""
    fast_path: bool = False
    llm_call_count: int = 0
    fallback_count: int = 0
    fallback_triggered: bool = False
    fallback_layer: str = ""
    fallback_reason: str = ""
    fallback_action: str = ""
    fallback_user_visible: bool = False
    fallback_recovered: bool = False
    fallback_original_route: str = ""
    fallback_final_route: str = ""
    post_turn_scheduled: bool = False
    post_turn_schedule_error: str = ""
    path_contract: PathContractStatus = PathContractStatus.UNKNOWN
    path_contract_reason: str = "not_finalized"
    rewrite: PathComponentMetrics = field(default_factory=PathComponentMetrics)
    rag_router: PathComponentMetrics = field(default_factory=PathComponentMetrics)
    rag: PathComponentMetrics = field(default_factory=PathComponentMetrics)
    supervisor: PathComponentMetrics = field(default_factory=PathComponentMetrics)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any] | None) -> "PathMetrics":
        if not value:
            return cls()
        status_raw = str(value.get("path_contract") or PathContractStatus.UNKNOWN.value)
        try:
            status = PathContractStatus(status_raw)
        except ValueError:
            status = PathContractStatus.UNKNOWN
        return cls(
            turn_type=str(value.get("turn_type") or ""),
            turn_type_reason=str(value.get("turn_type_reason") or ""),
            fast_path=bool(value.get("fast_path", False)),
            llm_call_count=int(value.get("llm_call_count") or 0),
            fallback_count=int(value.get("fallback_count") or 0),
            fallback_triggered=bool(value.get("fallback_triggered", False)),
            fallback_layer=str(value.get("fallback_layer") or ""),
            fallback_reason=str(value.get("fallback_reason") or ""),
            fallback_action=str(value.get("fallback_action") or ""),
            fallback_user_visible=bool(value.get("fallback_user_visible", False)),
            fallback_recovered=bool(value.get("fallback_recovered", False)),
            fallback_original_route=str(value.get("fallback_original_route") or ""),
            fallback_final_route=str(value.get("fallback_final_route") or ""),
            post_turn_scheduled=bool(value.get("post_turn_scheduled", False)),
            post_turn_schedule_error=str(value.get("post_turn_schedule_error") or ""),
            path_contract=status,
            path_contract_reason=str(value.get("path_contract_reason") or "not_finalized"),
            rewrite=PathComponentMetrics.from_mapping(value.get("rewrite")),
            rag_router=PathComponentMetrics.from_mapping(value.get("rag_router")),
            rag=PathComponentMetrics.from_mapping(value.get("rag")),
            supervisor=PathComponentMetrics.from_mapping(value.get("supervisor")),
        )

    def to_legacy_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["path_contract"] = self.path_contract.value
        for component in COMPONENTS:
            data[component] = asdict(getattr(self, component))
        return data

    def with_component(
        self,
        component: PathComponent,
        *,
        should_call: bool | None = None,
        called: bool | None = None,
    ) -> "PathMetrics":
        current = getattr(self, component)
        updated = PathComponentMetrics(
            should_call=current.should_call if should_call is None else bool(should_call),
            called=current.called if called is None else bool(called),
        )
        values = self.to_legacy_dict()
        values[component] = asdict(updated)
        return PathMetrics.from_mapping(values)
