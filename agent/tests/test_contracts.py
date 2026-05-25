"""Contracts package tests for typed runtime objects and legacy adapters."""

from __future__ import annotations

from pathlib import Path

import pytest
from langchain_core.messages import HumanMessage
from pydantic import ValidationError

from contracts.context import ContextBudget, ContextBundle, ContextSources
from contracts.events import ObservabilityEvent, ObservabilityEventType
from contracts.execution import ExecutorDecision, ExecutorType
from contracts.path import (
    COMPONENTS,
    PathComponentMetrics,
    PathContractStatus,
    PathMetrics,
)
from contracts.rag import RagChunk, RagResult
from contracts.routing import TurnType, TurnTypeDecision
from contracts.sse import validate_sse_event
from gateway.schemas import ClientAction
from graph.executors import ExecutorType as GraphExecutorType
from graph.turn_type import TurnType as GraphTurnType
from memory.assembly import ContextBudgetResult
from observability.path_contract import new_path_metrics, update_path_component
from rag.retriever import RagChunk as RetrieverRagChunk


def test_routing_and_execution_contracts_preserve_existing_values() -> None:
    assert TurnType.FACT_UPDATE.value == "fact_update"
    assert TurnType.MEMORY_QUERY.value == "memory_query"
    assert TurnType.CLIENT_ACTION.value == "client_action"
    assert ExecutorType.MEMORY_QUERY.value == "memory_query_executor"
    assert ExecutorType.RAG_ANSWER.value == "rag_answer_executor"
    assert ExecutorType.DEEPAGENTS.value == "deepagents_executor"

    turn = TurnTypeDecision(TurnType.KNOWLEDGE_QUERY, "knowledge_intent_rule")
    decision = ExecutorDecision(ExecutorType.RAG_ANSWER, "rag_chunks_available_score_0.92")

    assert turn.turn_type is GraphTurnType.KNOWLEDGE_QUERY
    assert decision.executor is GraphExecutorType.RAG_ANSWER
    assert decision.reason == "rag_chunks_available_score_0.92"


def test_path_metrics_round_trips_to_legacy_dict_shape() -> None:
    metrics = PathMetrics(
        turn_type="knowledge_query",
        turn_type_reason="knowledge_intent_rule",
        rag=PathComponentMetrics(should_call=True, called=True),
        path_contract=PathContractStatus.PASS,
        path_contract_reason="ok",
    )

    legacy = metrics.to_legacy_dict()
    restored = PathMetrics.from_mapping(legacy)

    assert tuple(COMPONENTS) == ("rewrite", "rag_router", "rag", "supervisor")
    assert legacy["path_contract"] == "pass"
    assert legacy["rag"] == {"should_call": True, "called": True}
    assert restored == metrics


def test_path_contract_module_keeps_legacy_dict_api() -> None:
    metrics = new_path_metrics(turn_type="chitchat", turn_type_reason="chitchat_rule")
    updated = update_path_component(metrics, "supervisor", should_call=False, called=False)

    assert updated["turn_type"] == "chitchat"
    assert updated["path_contract"] == "unknown"
    assert updated["supervisor"] == {"should_call": False, "called": False}


def test_context_budget_alias_preserves_existing_metadata_api() -> None:
    budget = ContextBudgetResult(
        system_prompt_len=12,
        user_memory_count=2,
        memory_profile_count=1,
        memory_free_text_count=1,
        rag_chunk_count=3,
        message_count=4,
        message_chars=40,
        budget_truncated=False,
    )

    assert isinstance(budget, ContextBudget)
    assert budget.as_metadata()["rag_chunk_count"] == 3


def test_context_bundle_contract_carries_sources_and_budget() -> None:
    message = HumanMessage(content="当前问题")
    chunk = RetrieverRagChunk(doc_id="doc-1", chunk_id="c-1", text="policy", score=0.9)
    budget = ContextBudget(
        system_prompt_len=6,
        user_memory_count=1,
        memory_profile_count=0,
        memory_free_text_count=1,
        rag_chunk_count=1,
        message_count=1,
        message_chars=4,
        budget_truncated=False,
    )
    sources = ContextSources(
        user_memories=("偏好短答",),
        summary="摘要",
        rag_chunks=(chunk,),
        current_human="当前问题",
        original_human=None,
    )
    bundle = ContextBundle(
        system_prompt="system",
        model_messages=(message,),
        budget=budget,
        sources=sources,
    )

    assert bundle.messages == [message]
    assert bundle.budget_metadata()["message_count"] == 1
    assert bundle.sources.as_metadata()["source_rag_chunk_count"] == 1


def test_rag_contract_is_compatible_with_retriever_chunk() -> None:
    chunk = RetrieverRagChunk(doc_id="doc-1", chunk_id="c-1", text="policy", score=0.9)
    result = RagResult.from_chunks([chunk], query="报销制度", role_id="role-sales")

    assert isinstance(chunk, RagChunk)
    assert chunk.to_dict() == {
        "doc_id": "doc-1",
        "chunk_id": "c-1",
        "text": "policy",
        "score": 0.9,
    }
    assert result.chunks == (chunk,)
    assert result.skipped is False


def test_rag_chunk_can_carry_channel_metadata_without_breaking_legacy_shape() -> None:
    chunk = RagChunk(
        doc_id="doc-1",
        chunk_id="c-1",
        text="policy",
        score=0.9,
        channel="bm25",
        metadata={"source": "fallback"},
    )

    assert chunk.to_dict()["channel"] == "bm25"
    assert chunk.to_dict()["metadata"] == {"source": "fallback"}


def test_pyproject_declares_domain_and_infrastructure_packages() -> None:
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")

    assert '"domain"' in text
    assert '"infrastructure"' in text


def test_sse_contract_validates_all_current_event_shapes() -> None:
    action = ClientAction(tool="jumpPage", args={"page": "pageA"}, requires_approval=False)
    payloads = [
        {"type": "token", "content": "hi", "segment_id": "seg-1"},
        {"type": "done"},
        {"type": "client_actions", "client_actions": [action.model_dump()]},
        {"type": "retract", "segment_id": "seg-1", "reason": "outbound_guard"},
        {"type": "replace", "segment_id": "seg-1", "content": "safe"},
        {"type": "error", "message": "failed"},
    ]

    assert [validate_sse_event(payload).type for payload in payloads] == [
        "token",
        "done",
        "client_actions",
        "retract",
        "replace",
        "error",
    ]


def test_sse_contract_rejects_unknown_or_extra_fields() -> None:
    with pytest.raises(ValidationError):
        validate_sse_event({"type": "unknown"})

    with pytest.raises(ValidationError):
        validate_sse_event({"type": "done", "content": "extra"})


def test_observability_event_contract_is_immutable() -> None:
    event = ObservabilityEvent(
        ObservabilityEventType.PATH_METRICS_FINALIZED,
        {"path_contract": "pass"},
    )

    assert event.name == "path_metrics.finalized"
    assert event.metadata == {"path_contract": "pass"}
    with pytest.raises(Exception):
        event.name = "changed"  # type: ignore[misc]


def test_pyproject_declares_contracts_top_level_package() -> None:
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")

    assert '"contracts"' in text
