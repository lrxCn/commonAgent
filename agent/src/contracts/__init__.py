"""Stable cross-module runtime contracts for the Agent service."""

from contracts.context import ContextBudget, ContextBundle, ContextSources
from contracts.events import ObservabilityEvent
from contracts.execution import ExecutorDecision, ExecutorReason, ExecutorType
from contracts.fallback import FallbackAction, FallbackDecision, FallbackLayer
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
from contracts.memory_store import (
    MEMORY_STORE_FACTS_SEGMENT,
    MEMORY_STORE_PROFILE_SEGMENT,
    MEMORY_STORE_USERS_PREFIX,
    MemoryStoreNamespace,
    ProfileMemoryValue,
    UserMemoryReadResult,
    facts_namespace,
    profile_namespace,
)
from contracts.memory_write import (
    ExtractionMethod,
    MemorySubject,
    MemoryWriteExpectation,
    MemoryWriteMode,
    StructuredMemoryRecord,
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
    "ExtractionMethod",
    "FallbackAction",
    "FallbackDecision",
    "FallbackLayer",
    "IntentDecision",
    "IntentDomain",
    "IntentFeedback",
    "IntentOperation",
    "IntentRisk",
    "IntentRoute",
    "MemoryStoreNamespace",
    "MemorySubject",
    "MemoryWriteExpectation",
    "MemoryWriteMode",
    "MEMORY_STORE_FACTS_SEGMENT",
    "MEMORY_STORE_PROFILE_SEGMENT",
    "MEMORY_STORE_USERS_PREFIX",
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
    "ProfileMemoryValue",
    "RagChunk",
    "RagResult",
    "ReplaceSseEvent",
    "RetractSseEvent",
    "SseEvent",
    "SseEventType",
    "SpeechAct",
    "StructuredMemoryRecord",
    "TokenSseEvent",
    "TurnReason",
    "TurnType",
    "TurnTypeDecision",
    "UserMemoryReadResult",
    "validate_sse_event",
    "facts_namespace",
    "profile_namespace",
]
