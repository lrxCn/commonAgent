"""Tests for rag.retriever — hybrid retrieval (mocked; no live Qdrant)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from qdrant_client.http import models as qmodels

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


def _matches_filter(payload: dict[str, Any], flt: qmodels.Filter | None) -> bool:
    if flt is None:
        return True
    if flt.should:
        return any(_matches_filter(payload, qmodels.Filter(must=[cond])) for cond in flt.should)
    if flt.must:
        for cond in flt.must:
            key = cond.key
            match = cond.match
            if isinstance(match, qmodels.MatchValue) and payload.get(key) != match.value:
                return False
            if isinstance(match, qmodels.MatchText):
                needle = match.text.strip().lower()
                haystack = str(payload.get(key) or "").lower()
                if needle not in haystack:
                    return False
    return True


class LexicalFakeQdrant:
    """Role-scoped scroll fake for BM25 fallback tests."""

    def __init__(self, payloads: list[dict[str, Any]]) -> None:
        self.payloads = payloads

    def get_collection(self, collection_name: str) -> MagicMock:
        return MagicMock(config=MagicMock(params=MagicMock(sparse_vectors=None)))

    def scroll(
        self,
        collection_name: str,
        scroll_filter: qmodels.Filter | None = None,
        limit: int = 10,
        with_payload: bool = True,
    ) -> tuple[list[MagicMock], None]:
        records: list[MagicMock] = []
        for payload in self.payloads:
            if not _matches_filter(payload, scroll_filter):
                continue
            point = MagicMock()
            point.payload = payload
            point.id = payload["chunk_id"]
            records.append(point)
            if len(records) >= limit:
                break
        return records, None


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


def test_empty_role_ids_returns_empty() -> None:
    set_settings_override(_settings(QDRANT_MOCK=True))
    assert retrieve([], "报销制度") == []


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
            "role_ids": ["role-sales"],
            "rewritten_query": "报销制度",
            "rag_skipped": True,
        }
    )
    assert out["rag_chunks"] == []


def test_rag_retrieval_node_populates_chunks() -> None:
    set_settings_override(_settings(QDRANT_MOCK=True))
    out = rag_retrieval_node(
        {
            "role_ids": ["role-sales"],
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


def test_bm25_fallback_recalls_keyword_hit_when_dense_empty() -> None:
    set_settings_override(_settings(QDRANT_MOCK=False, RERANK_TOP_K=5))
    set_embed_query(lambda _q: [0.0] * 1024)
    set_reranker(lambda _q, docs: [1.0 if "差旅报销专项SIGMA" in doc else 0.1 for doc in docs])
    mock_client = MagicMock()
    mock_client.search.return_value = []
    mock_client.get_collection.return_value = MagicMock(
        config=MagicMock(params=MagicMock(sparse_vectors=None))
    )
    payloads = [
        {
            "role_id": "role-sales",
            "doc_id": "doc-policy",
            "chunk_id": "chunk-policy",
            "text": "差旅报销专项SIGMA：出差结束后30日内提交。",
        },
        {
            "role_id": "role-sales",
            "doc_id": "doc-random",
            "chunk_id": "chunk-random",
            "text": "会议室使用规则：提前一天预约。",
        },
    ]

    def _scroll(
        collection_name: str,
        scroll_filter: qmodels.Filter | None = None,
        limit: int = 10,
        with_payload: bool = True,
    ) -> tuple[list[MagicMock], None]:
        records: list[MagicMock] = []
        for payload in payloads:
            point = MagicMock()
            point.payload = payload
            point.id = payload["chunk_id"]
            records.append(point)
        return records[:limit], None

    mock_client.scroll = _scroll
    set_qdrant_client(mock_client)

    chunks = retrieve("role-sales", "差旅报销专项SIGMA")
    assert chunks
    assert chunks[0].doc_id == "doc-policy"
    assert "差旅报销专项SIGMA" in chunks[0].text


def test_bm25_fallback_respects_role_id_filter_when_embedding_fails() -> None:
    set_settings_override(_settings(QDRANT_MOCK=False, RERANK_TOP_K=5))

    def _raise_embed(_query: str) -> list[float]:
        raise RuntimeError("embedding unavailable")

    set_embed_query(_raise_embed)
    set_reranker(lambda _q, docs: [float(len(docs) - i) for i, _ in enumerate(docs)])
    set_qdrant_client(  # type: ignore[arg-type]
        LexicalFakeQdrant(
            [
                {
                    "role_id": "role-sales",
                    "doc_id": "doc-sales-secret",
                    "chunk_id": "chunk-sales",
                    "text": "内部返点策略DELTA 只允许销售角色查看。",
                },
                {
                    "role_id": "role-hr",
                    "doc_id": "doc-hr-public",
                    "chunk_id": "chunk-hr",
                    "text": "年假政策DELTA 面向HR角色。",
                },
            ]
        )
    )

    chunks = retrieve("role-hr", "内部返点策略DELTA")
    assert not any(chunk.doc_id == "doc-sales-secret" for chunk in chunks)
    assert [chunk.doc_id for chunk in chunks] == ["doc-hr-public"]


def test_hybrid_merge_reranks_dense_and_bm25_candidates() -> None:
    set_settings_override(_settings(QDRANT_MOCK=False, RERANK_TOP_K=5))
    set_embed_query(lambda _q: [0.1] * 1024)
    set_reranker(lambda _q, docs: [1.0 if "精确关键词KAPPA" in doc else 0.2 for doc in docs])

    dense_hit = MagicMock()
    dense_hit.score = 0.99
    dense_hit.id = "dense-c"
    dense_hit.payload = {
        "role_id": "role-sales",
        "doc_id": "doc-dense",
        "chunk_id": "dense-c",
        "text": "泛化报销政策说明，没有精确关键词。",
    }
    client = MagicMock()
    client.search.return_value = [dense_hit]
    client.get_collection.return_value = MagicMock(
        config=MagicMock(params=MagicMock(sparse_vectors=None))
    )
    client.scroll.return_value = (
        [
            MagicMock(
                id="bm25-c",
                payload={
                    "role_id": "role-sales",
                    "doc_id": "doc-bm25",
                    "chunk_id": "bm25-c",
                    "text": "精确关键词KAPPA 对应的知识库条款。",
                },
            )
        ],
        None,
    )
    set_qdrant_client(client)

    chunks = retrieve("role-sales", "精确关键词KAPPA")
    assert [chunk.doc_id for chunk in chunks[:2]] == ["doc-bm25", "doc-dense"]


def test_build_retrieval_metadata_fields() -> None:
    meta = build_retrieval_metadata(
        role_ids=["role-sales"],
        query="报销",
        dense_count=3,
        sparse_count=1,
        result_count=2,
        mock=False,
    )
    assert meta["rag.role_ids"] == ["role-sales"]
    assert meta["rag.dense_hits"] == 3
    assert meta["rag.result_count"] == 2
    assert meta["rag.mock"] is False
    assert meta["rag.second_pass"] is False


def test_build_retrieval_metadata_second_pass_flag() -> None:
    meta = build_retrieval_metadata(
        role_ids=["role-sales"],
        query="q",
        dense_count=0,
        sparse_count=0,
        result_count=1,
        mock=True,
        second_pass=True,
    )
    assert meta["rag.second_pass"] is True
