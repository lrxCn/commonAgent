"""Structured intent contracts for the Agent control plane."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from contracts.routing import TurnType


class SpeechAct(str, Enum):
    """User utterance shape independent from execution route."""

    STATEMENT = "statement"
    QUESTION = "question"
    COMMAND = "command"
    CHITCHAT = "chitchat"
    UNSAFE = "unsafe"
    UNCLEAR = "unclear"


class IntentDomain(str, Enum):
    """Target domain the user is asking the Agent to operate on."""

    USER_MEMORY = "user_memory"
    ORG_MEMORY = "org_memory"
    KNOWLEDGE_BASE = "knowledge_base"
    CLIENT_TOOL = "client_tool"
    OPEN_CHAT = "open_chat"
    SAFETY = "safety"
    UNKNOWN = "unknown"


class IntentOperation(str, Enum):
    """Capability-plane operation requested by an intent decision."""

    MEMORY_WRITE = "memory_write"
    MEMORY_READ = "memory_read"
    KB_RETRIEVE = "kb_retrieve"
    CLIENT_ACTION = "client_action"
    ANSWER = "answer"
    CLARIFY = "clarify"
    REJECT = "reject"


class IntentRoute(str, Enum):
    """Compatibility route consumed by existing graph/path contracts."""

    FACT_UPDATE = "fact_update"
    MEMORY_QUERY = "memory_query"
    KNOWLEDGE_QUERY = "knowledge_query"
    CLIENT_ACTION = "client_action"
    CHITCHAT = "chitchat"
    AMBIGUOUS = "ambiguous"
    GENERAL_CHAT = "general_chat"
    SAFETY_REFUSAL = "safety_refusal"


class IntentRisk(str, Enum):
    """Risk level for misrouting or executing the requested operation."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


_ROUTE_TO_TURN_TYPE: dict[IntentRoute, TurnType] = {
    IntentRoute.FACT_UPDATE: TurnType.FACT_UPDATE,
    IntentRoute.MEMORY_QUERY: TurnType.MEMORY_QUERY,
    IntentRoute.KNOWLEDGE_QUERY: TurnType.KNOWLEDGE_QUERY,
    IntentRoute.CLIENT_ACTION: TurnType.CLIENT_ACTION,
    IntentRoute.CHITCHAT: TurnType.CHITCHAT,
    IntentRoute.AMBIGUOUS: TurnType.AMBIGUOUS,
    IntentRoute.GENERAL_CHAT: TurnType.GENERAL_CHAT,
    IntentRoute.SAFETY_REFUSAL: TurnType.SAFETY_REFUSAL,
}


class IntentDecision(BaseModel):
    """Full structured intent decision emitted by the future control plane."""

    model_config = ConfigDict(extra="forbid", use_enum_values=True, frozen=True)

    speech_act: SpeechAct
    domain: IntentDomain
    operation: IntentOperation
    route: IntentRoute
    confidence: float = Field(ge=0.0, le=1.0)
    risk: IntentRisk
    reasons: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    needs_clarification: bool = False

    @field_validator("reasons", "evidence")
    @classmethod
    def _reject_blank_items(cls, value: list[str]) -> list[str]:
        if any(not item.strip() for item in value):
            raise ValueError("blank intent reason or evidence item")
        return value

    @property
    def turn_type(self) -> TurnType:
        """Return the legacy turn_type compatibility value derived from route."""
        return _ROUTE_TO_TURN_TYPE[IntentRoute(self.route)]

    @property
    def turn_type_reason(self) -> str:
        """Return the legacy turn_type reason derived from the first reason code."""
        return self.reasons[0] if self.reasons else "intent_decision"

    def to_trace_dict(self) -> dict[str, object]:
        """Serialize to a stable dict shape for traces, evals, and metadata."""
        payload = self.model_dump(mode="json")
        payload["turn_type"] = self.turn_type.value
        payload["turn_type_reason"] = self.turn_type_reason
        return payload


class IntentFeedback(BaseModel):
    """Structured correction signal used by later feedback/eval tasks."""

    model_config = ConfigDict(extra="forbid", use_enum_values=True, frozen=True)

    input: str
    predicted_route: IntentRoute
    corrected_route: IntentRoute | None = None
    reason: str
    source: str = "user"
