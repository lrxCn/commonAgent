"""Stable cross-module runtime contracts for the Agent service."""

from contracts.context import ContextBudget, ContextBundle, ContextSources
from contracts.events import ObservabilityEvent
from contracts.execution import ExecutorDecision, ExecutorReason, ExecutorType
from contracts.intent import (
    IntentDecision,
    IntentDomain,
    IntentFeedback,
    IntentOperation,
    IntentRisk,
    IntentRoute,
    SpeechAct,
)
from contracts.llm import (
    ChatModelPolicy,
    EmbeddingModelPolicy,
    ModelCallMetadata,
    ModelUseCase,
    RerankModelPolicy,
)
from contracts.path import (
    COMPONENTS,
    LLM_COMPONENTS,
    PathComponent,
    PathComponentMetrics,
    PathContractStatus,
    PathMetrics,
)
from contracts.rag import RagChunk, RagResult
from contracts.routing import TurnReason, TurnType, TurnTypeDecision
from contracts.sse import (
    ClientActionsSseEvent,
    DoneSseEvent,
    ErrorSseEvent,
    ReplaceSseEvent,
    RetractSseEvent,
    SseEvent,
    SseEventType,
    TokenSseEvent,
    validate_sse_event,
)

__all__ = [
    "COMPONENTS",
    "LLM_COMPONENTS",
    "ClientActionsSseEvent",
    "ContextBudget",
    "ContextBundle",
    "ContextSources",
    "DoneSseEvent",
    "ErrorSseEvent",
    "ExecutorDecision",
    "ExecutorReason",
    "ExecutorType",
    "IntentDecision",
    "IntentDomain",
    "IntentFeedback",
    "IntentOperation",
    "IntentRisk",
    "IntentRoute",
    "ChatModelPolicy",
    "EmbeddingModelPolicy",
    "ModelCallMetadata",
    "ModelUseCase",
    "RerankModelPolicy",
    "ObservabilityEvent",
    "PathComponent",
    "PathComponentMetrics",
    "PathContractStatus",
    "PathMetrics",
    "RagChunk",
    "RagResult",
    "ReplaceSseEvent",
    "RetractSseEvent",
    "SseEvent",
    "SseEventType",
    "SpeechAct",
    "TokenSseEvent",
    "TurnReason",
    "TurnType",
    "TurnTypeDecision",
    "validate_sse_event",
]
