"""Tests for rag.retriever — hybrid retrieval (mocked; no live Qdrant)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from rag.retriever import (
    RagChunk,
    build_retrieval_metadata,
    format_rag_chunks_for_system,
    rag_retrieval_node,
    reset_retriever_overrides,
    retrieve,
    rerank_candidates,
    set_embed_query,
    set_qdrant_client,
    set_reranker,
)
from settings.config import Settings, reset_settings, set_settings_override

_REQUIRED_ENV = {
    "LANGSMITH_API_KEY": "lsv2_test",
    "OPENAI_API_KEY": "sk-test",
    "DATABASE_URL": "postgresql://postgres:test@localhost:5432/common_agent",
}


@pytest.fixture(autouse=True)
def _clean_retriever_and_settings() -> None:
    reset_retriever_overrides()
    reset_settings()
    yield
    reset_retriever_overrides()
    reset_settings()


def _settings(**extra: object) -> Settings:
    return Settings(**{**_REQUIRED_ENV, **extra})  # type: ignore[arg-type]


def test_mock_retrieve_filters_by_role_id() -> None:
    set_settings_override(_settings(QDRANT_MOCK=True, RERANK_TOP_K=10))
    chunks = retrieve("role-sales", "报销制度")
    assert len(chunks) == 2
    assert all(c.doc_id == "doc-reimbursement" for c in chunks)
    assert all(c.chunk_id and c.text for c in chunks)


def test_mock_retrieve_unknown_role_returns_empty() -> None:
    set_settings_override(_settings(QDRANT_MOCK=True))
    assert retrieve("role-unknown", "报销") == []


def test_mock_retrieve_respects_top_k() -> None:
    set_settings_override(_settings(QDRANT_MOCK=True, RERANK_TOP_K=1))
    chunks = retrieve("role-sales", "报销制度")
    assert len(chunks) <= 1


def test_empty_query_returns_empty_without_error() -> None:
    set_settings_override(_settings(QDRANT_MOCK=True))
    assert retrieve("role-sales", "") == []
    assert retrieve("role-sales", "   ") == []


def test_empty_role_id_returns_empty() -> None:
    set_settings_override(_settings(QDRANT_MOCK=True))
    assert retrieve("", "报销制度") == []


def test_rag_chunks_include_doc_id_and_chunk_id() -> None:
    set_settings_override(_settings(QDRANT_MOCK=True))
    chunk = retrieve("role-hr", "年假")[0]
    assert chunk.doc_id == "doc-leave"
    assert chunk.chunk_id == "chunk-010"
    assert "年假" in chunk.text
    assert chunk.score > 0


def test_format_rag_chunks_includes_citation_markers() -> None:
    chunk = RagChunk(doc_id="d1", chunk_id="c1", text="示例文本", score=0.9)
    text = format_rag_chunks_for_system([chunk])
    assert "[doc:d1/chunk:c1]" in text
    assert "示例文本" in text


def test_rerank_candidates_limits_to_top_k() -> None:
    set_settings_override(_settings(RERANK_TOP_K=2))
    set_reranker(lambda _q, docs: [float(i) for i in range(len(docs))])
    candidates = [
        {"doc_id": "d1", "chunk_id": f"c{i}", "text": f"t{i}", "score": 0.5}
        for i in range(5)
    ]
    chunks = rerank_candidates("q", candidates, top_k=2)
    assert len(chunks) == 2


def test_rag_retrieval_node_skipped_when_router_skipped() -> None:
    set_settings_override(_settings(QDRANT_MOCK=True))
    out = rag_retrieval_node(
        {
            "role_id": "role-sales",
            "rewritten_query": "报销制度",
            "rag_skipped": True,
        }
    )
    assert out["rag_chunks"] == []


def test_rag_retrieval_node_populates_chunks() -> None:
    set_settings_override(_settings(QDRANT_MOCK=True))
    out = rag_retrieval_node(
        {
            "role_id": "role-sales",
            "rewritten_query": "报销制度是什么",
            "rag_skipped": False,
        }
    )
    assert len(out["rag_chunks"]) >= 1
    assert isinstance(out["rag_chunks"][0], RagChunk)


def test_live_path_empty_qdrant_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    set_settings_override(_settings(QDRANT_MOCK=False, RERANK_TOP_K=5))
    set_embed_query(lambda _q: [0.1] * 1024)

    mock_client = MagicMock()
    mock_client.search.return_value = []
    mock_client.scroll.return_value = ([], None)
    mock_client.get_collection.return_value = MagicMock(
        config=MagicMock(params=MagicMock(sparse_vectors=None))
    )
    set_qdrant_client(mock_client)

    chunks = retrieve("role-sales", "报销制度")
    assert chunks == []


def test_build_retrieval_metadata_fields() -> None:
    meta = build_retrieval_metadata(
        role_id="role-sales",
        query="报销",
        dense_count=3,
        sparse_count=1,
        result_count=2,
        mock=False,
    )
    assert meta["rag.role_id"] == "role-sales"
    assert meta["rag.dense_hits"] == 3
    assert meta["rag.result_count"] == 2
    assert meta["rag.mock"] is False
