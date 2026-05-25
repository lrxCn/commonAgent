"""Tests for RagSubAgent second-pass retrieval and graph routing."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from gateway.schemas import RequestContext
from graph.build import compile_graph
from graph.context import graph_context_from_request
from graph.nodes import route_after_rag_retrieval
from graph.rag_subagent import (
    apply_rag_subagent_merge,
    max_chunk_score,
    merge_rag_chunks,
    run_rag_subagent_retrieval,
    second_pass_top_k,
    should_delegate_rag_subagent,
)
from graph.supervisor import reset_supervisor_overrides, set_answer_invoke, set_supervisor_invoke
from rag.retriever import RagChunk, reset_retriever_overrides
from rag.rewrite import set_rewrite_llm
from rag.router import set_router_classifier
from settings.config import Settings, reset_settings, set_settings_override

_REQUIRED_ENV = {
    "LANGSMITH_API_KEY": "lsv2_test",
    "OPENAI_API_KEY": "sk-test",
    "DATABASE_URL": "postgresql://postgres:test@localhost:5432/common_agent",
    "GUARDRAILS_ENABLED": False,
    "MEMORY_STORE_MOCK": True,
    "QDRANT_MOCK": True,
    "RAG_ROUTER_MODE": "rules",
}


@pytest.fixture(autouse=True)
def _clean(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("graph.nodes.load_thread_messages", lambda _thread_id: [])
    monkeypatch.setattr("graph.nodes.get_rolling_summary", lambda _thread_id: None)
    monkeypatch.setattr("graph.nodes.schedule_post_turn_jobs", lambda **_kwargs: None)
    reset_retriever_overrides()
    reset_supervisor_overrides()
    reset_settings()
    yield
    reset_retriever_overrides()
    reset_supervisor_overrides()
    reset_settings()


def _settings(**extra: object) -> Settings:
    return Settings(**{**_REQUIRED_ENV, **extra})  # type: ignore[arg-type]


def _chunk(
    *,
    doc_id: str = "doc-1",
    chunk_id: str = "c-1",
    text: str = "text",
    score: float,
) -> RagChunk:
    return RagChunk(doc_id=doc_id, chunk_id=chunk_id, text=text, score=score)


def test_should_delegate_when_chunks_empty() -> None:
    cfg = _settings()
    assert should_delegate_rag_subagent(rag_skipped=False, rag_chunks=[], settings=cfg) is True


def test_should_not_delegate_when_rag_skipped() -> None:
    cfg = _settings()
    assert (
        should_delegate_rag_subagent(
            rag_skipped=True,
            rag_chunks=[],
            settings=cfg,
        )
        is False
    )


def test_should_not_delegate_when_high_score() -> None:
    cfg = _settings(RAG_SUBAGENT_SCORE_THRESHOLD=0.3)
    chunks = [_chunk(score=0.85)]
    assert should_delegate_rag_subagent(rag_skipped=False, rag_chunks=chunks, settings=cfg) is False


def test_should_delegate_when_score_below_threshold() -> None:
    cfg = _settings(RAG_SUBAGENT_SCORE_THRESHOLD=0.3)
    chunks = [_chunk(score=0.2)]
    assert should_delegate_rag_subagent(rag_skipped=False, rag_chunks=chunks, settings=cfg) is True


def test_merge_dedupes_by_chunk_id_keeps_higher_score() -> None:
    primary = [_chunk(chunk_id="c-1", score=0.4, text="a")]
    secondary = [_chunk(chunk_id="c-1", score=0.9, text="b"), _chunk(chunk_id="c-2", score=0.5, text="c")]
    merged = merge_rag_chunks(primary, secondary, max_chunks=10)
    assert len(merged) == 2
    by_id = {c.chunk_id: c for c in merged}
    assert by_id["c-1"].score == 0.9
    assert by_id["c-1"].text == "b"


def test_merge_respects_max_chunks() -> None:
    cfg = _settings(RAG_CHUNKS_MAX=2)
    primary = [_chunk(chunk_id=f"p{i}", score=0.9 - i * 0.1) for i in range(3)]
    secondary = [_chunk(chunk_id=f"s{i}", score=0.5 - i * 0.01) for i in range(3)]
    merged = merge_rag_chunks(primary, secondary, settings=cfg)
    assert len(merged) <= 2


def test_route_after_rag_retrieval_to_subagent() -> None:
    cfg = _settings()
    set_settings_override(cfg)
    assert route_after_rag_retrieval({"rag_skipped": False, "rag_chunks": []}) == "rag_subagent"


def test_route_after_rag_retrieval_skips_subagent_for_quality() -> None:
    cfg = _settings(RAG_SUBAGENT_SCORE_THRESHOLD=0.3)
    set_settings_override(cfg)
    state = {
        "rag_skipped": False,
        "rag_chunks": [_chunk(score=0.9)],
    }
    assert route_after_rag_retrieval(state) == "context_assembly"


def test_run_rag_subagent_retrieval_sets_second_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    set_settings_override(_settings(QDRANT_MOCK=True, RERANK_TOP_K=5))
    calls: list[dict[str, object]] = []

    def _spy(role_id: str, query: str, **kwargs):  # type: ignore[no-untyped-def]
        calls.append(kwargs)
        return [_chunk(score=0.8)]

    monkeypatch.setattr("graph.rag_subagent.retrieve", _spy)
    chunks = run_rag_subagent_retrieval("role-sales", "报销制度", settings=_settings(RERANK_TOP_K=5))
    assert len(chunks) == 1
    assert calls[0]["second_pass"] is True
    assert calls[0]["top_k"] == second_pass_top_k(_settings(RERANK_TOP_K=5))


def test_graph_triggers_second_retrieve_on_empty_primary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_settings_override(_settings())
    set_rewrite_llm(lambda _prompt: "rewritten query")
    set_router_classifier(lambda _prompt: '{"need_rag": true}')
    set_supervisor_invoke(
        lambda _system, messages: [AIMessage(content="ok")]
    )
    set_answer_invoke(lambda _system, messages: "ok")

    call_count = 0

    def _retrieve(role_id: str, query: str, **kwargs):  # type: ignore[no-untyped-def]
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return []
        return [_chunk(doc_id="doc-1", chunk_id="c-2", text="second pass", score=0.88)]

    monkeypatch.setattr("rag.retriever.retrieve", _retrieve)
    monkeypatch.setattr("graph.rag_subagent.retrieve", _retrieve)

    graph = compile_graph(checkpointer=MemorySaver(), use_pooled_postgres=False)
    result = graph.invoke(
        {"messages": [HumanMessage(content="报销制度？")]},
        context=graph_context_from_request(
            RequestContext(user_id="u1", role_id="role-sales", tools=[])
        ),
        config={"configurable": {"thread_id": "thread-rag-sub-1"}},
    )

    assert call_count == 2
    chunks = result.get("rag_chunks") or []
    assert len(chunks) == 1
    assert chunks[0].chunk_id == "c-2"


def test_graph_skips_second_retrieve_on_high_quality_primary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_settings_override(_settings(RAG_SUBAGENT_SCORE_THRESHOLD=0.3))
    set_rewrite_llm(lambda _prompt: "rewritten query")
    set_router_classifier(lambda _prompt: '{"need_rag": true}')
    set_supervisor_invoke(
        lambda _system, messages: [AIMessage(content="ok")]
    )
    set_answer_invoke(lambda _system, messages: "ok")

    retrieve_mock = MagicMock(
        return_value=[_chunk(doc_id="doc-1", chunk_id="c-1", text="good", score=0.9)]
    )
    monkeypatch.setattr("rag.retriever.retrieve", retrieve_mock)

    graph = compile_graph(checkpointer=MemorySaver(), use_pooled_postgres=False)
    graph.invoke(
        {"messages": [HumanMessage(content="报销制度？")]},
        context=graph_context_from_request(
            RequestContext(user_id="u1", role_id="role-sales", tools=[])
        ),
        config={"configurable": {"thread_id": "thread-rag-sub-2"}},
    )

    assert retrieve_mock.call_count == 1
    assert retrieve_mock.call_args.kwargs.get("second_pass") is not True


def test_apply_merge_caps_total_chunks() -> None:
    cfg = _settings(RAG_CHUNKS_MAX=3)
    primary = [_chunk(chunk_id=f"p{i}", score=0.9 - i * 0.05) for i in range(5)]
    secondary = [_chunk(chunk_id=f"s{i}", score=0.8 - i * 0.05) for i in range(5)]
    merged = apply_rag_subagent_merge(primary, secondary, settings=cfg)
    assert len(merged) <= 3


def test_max_chunk_score_empty() -> None:
    assert max_chunk_score([]) == 0.0
