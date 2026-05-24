"""Agent-level fallback contracts for control-plane decisions."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, field_validator


class FallbackLayer(str, Enum):
    """Runtime layer where a fallback was triggered."""

    INTENT = "intent"
    MEMORY = "memory"
    RAG = "rag"
    TOOL = "tool"
    LLM = "llm"
    SCHEMA = "schema"
    OUTPUT_GUARD = "output_guard"
    CHECKPOINT = "checkpoint"


class FallbackAction(str, Enum):
    """Stable recovery or degradation action."""

    ASK_CLARIFICATION = "ask_clarification"
    CONSERVATIVE_EXECUTOR = "conservative_executor"
    DISABLE_FAST_PATH = "disable_fast_path"
    HONEST_MISSING_MEMORY = "honest_missing_memory"
    RECORD_BACKGROUND_FAILURE = "record_background_failure"
    REPORT_NO_SOURCE = "report_no_source"
    SECOND_PASS_RETRIEVAL = "second_pass_retrieval"
    TOOL_UNAVAILABLE_REPLY = "tool_unavailable_reply"
    REQUIRE_HITL = "require_hitl"
    RETRY_ONCE = "retry_once"
    DEGRADED_MODEL = "degraded_model"
    TEMPLATE_REPLY = "template_reply"
    REPAIR_ONCE = "repair_once"
    SAFE_ERROR_REPLY = "safe_error_reply"
    RETRACT_REPLACE_REFUSAL = "retract_replace_refusal"
    RECOVERABLE_ERROR = "recoverable_error"


class FallbackDecision(BaseModel):
    """A normalized fallback decision carried by graph metrics and traces."""

    model_config = ConfigDict(extra="forbid", use_enum_values=True, frozen=True)

    triggered: bool = True
    layer: FallbackLayer
    reason: str
    action: FallbackAction
    user_visible: bool = False
    recovered: bool = False
    original_route: str = ""
    final_route: str = ""

    @field_validator("reason")
    @classmethod
    def _reason_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("fallback reason cannot be blank")
        return value

    def to_trace_dict(self) -> dict[str, object]:
        """Return stable LangSmith/path metadata keys."""
        return {
            "fallback.triggered": self.triggered,
            "fallback.layer": self.layer,
            "fallback.reason": self.reason,
            "fallback.action": self.action,
            "fallback.user_visible": self.user_visible,
            "fallback.recovered": self.recovered,
            "fallback.original_route": self.original_route,
            "fallback.final_route": self.final_route,
        }
