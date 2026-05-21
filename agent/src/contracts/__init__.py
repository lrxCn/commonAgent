"""Stable cross-module runtime contracts for the Agent service."""

from contracts.context import ContextBudget
from contracts.events import ObservabilityEvent
from contracts.execution import ExecutorDecision, ExecutorReason, ExecutorType
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
    "DoneSseEvent",
    "ErrorSseEvent",
    "ExecutorDecision",
    "ExecutorReason",
    "ExecutorType",
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
    "TokenSseEvent",
    "TurnReason",
    "TurnType",
    "TurnTypeDecision",
    "validate_sse_event",
]
