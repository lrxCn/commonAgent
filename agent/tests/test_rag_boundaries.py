"""Focused tests for RAG module boundaries."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from qdrant_client.http import models as qmodels

from contracts.rag import RagChunk
from domain.rag.lexical import lexical_terms, score_bm25
from domain.rag.merge import merge_candidates
from domain.rag.models import RagCandidate, RagQueryPlan
from domain.rag.service import RagRetrievalService
from infrastructure.qdrant.kb_store import QdrantKbStore
from settings.config import Settings

_REQUIRED_ENV = {
    "LANGSMITH_API_KEY": "lsv2_test",
    "OPENAI_API_KEY": "sk-test",
    "DATABASE_URL": "postgresql://postgres:test@localhost:5432/common_agent",
}


def _settings(**extra: object) -> Settings:
    return Settings(**{**_REQUIRED_ENV, **extra})  # type: ignore[arg-type]


def _field_matches(payload: dict[str, Any], cond: qmodels.FieldCondition) -> bool:
    key = cond.key
    match = cond.match
    if isinstance(match, qmodels.MatchValue):
        value = match.value
        payload_val = payload.get(key)
        if isinstance(payload_val, list):
            return value in payload_val
        return payload_val == value
    if isinstance(match, qmodels.MatchText):
        needle = match.text.strip().lower()
        haystack = str(payload.get(key) or "").lower()
        return needle in haystack
    return True


def _matches_filter(payload: dict[str, Any], flt: qmodels.Filter | None) -> bool:
    if flt is None:
        return True
    if flt.should:
        return any(_field_matches(payload, cond) for cond in flt.should)
    if flt.must:
        for item in flt.must:
            if isinstance(item, qmodels.FieldCondition):
                if not _field_matches(payload, item):
                    return False
            elif isinstance(item, qmodels.Filter) and not _matches_filter(payload, item):
                return False
    return True


class ScrollOnlyQdrant:
    def __init__(self, payloads: list[dict[str, Any]]) -> None:
        self.payloads = payloads
        self.filters: list[qmodels.Filter | None] = []

    def get_collection(self, collection_name: str) -> MagicMock:
        return MagicMock(config=MagicMock(params=MagicMock(sparse_vectors=None)))

    def scroll(
        self,
        collection_name: str,
        scroll_filter: qmodels.Filter | None = None,
        limit: int = 10,
        with_payload: bool = True,
    ) -> tuple[list[MagicMock], None]:
        self.filters.append(scroll_filter)
        records: list[MagicMock] = []
        for payload in self.payloads:
            if not _matches_filter(payload, scroll_filter):
                continue
            records.append(MagicMock(payload=payload, id=payload["chunk_id"]))
            if len(records) >= limit:
                break
        return records, None


def test_lexical_tokenizer_extracts_cjk_ngrams_and_words() -> None:
    terms = lexical_terms("差旅报销 SIGMA_42")

    assert "差" in terms
    assert "差旅" in terms
    assert "差旅报销" in terms
    assert "sigma_42" in terms


def test_bm25_scores_exact_keyword_above_unrelated_candidate() -> None:
    candidates = [
        RagCandidate("doc-a", "c-a", "差旅报销专项SIGMA 需要30日内提交", 0.0, "bm25"),
        RagCandidate("doc-b", "c-b", "会议室预约规则", 0.0, "bm25"),
    ]

    scored = score_bm25("差旅报销专项SIGMA", candidates, limit=2)

    assert [item.doc_id for item in scored] == ["doc-a"]
    assert scored[0].score > 0


def test_merge_candidates_dedupes_by_chunk_id_with_rrf() -> None:
    dense = [RagCandidate("doc-a", "c-1", "dense", 0.9, "dense")]
    lexical = [
        RagCandidate("doc-a", "c-1", "bm25", 5.0, "bm25"),
        RagCandidate("doc-b", "c-2", "other", 4.0, "bm25"),
    ]

    merged = merge_candidates(dense, lexical)

    assert [item.chunk_id for item in merged] == ["c-1", "c-2"]
    assert merged[0].score > merged[1].score


def test_qdrant_store_applies_role_filter_before_bm25_scoring() -> None:
    client = ScrollOnlyQdrant(
        [
            {
                "role_id": "role-sales",
                "doc_id": "doc-sales-secret",
                "chunk_id": "chunk-sales",
                "text": "内部返点策略DELTA 只允许销售角色查看。",
            },
            {
                "role_id": "role-hr",
                "doc_id": "doc-hr",
                "chunk_id": "chunk-hr",
                "text": "年假政策DELTA 面向HR角色。",
            },
        ]
    )
    store = QdrantKbStore(client=client, collection="kb")  # type: ignore[arg-type]

    hits = store.bm25_search(role_ids=["role-hr"], query="内部返点策略DELTA", limit=5)

    assert [hit.doc_id for hit in hits] == ["doc-hr"]
    assert all(hit.doc_id != "doc-sales-secret" for hit in hits)


def test_rag_service_keeps_bm25_fallback_when_embedding_fails() -> None:
    class Store:
        def dense_search(self, **_kwargs: object) -> list[RagCandidate]:
            raise AssertionError("dense should be skipped when embedding fails")

        def lexical_search(self, **_kwargs: object) -> list[RagCandidate]:
            return [
                RagCandidate("doc-a", "c-a", "policy", 0.7, "bm25"),
            ]

    def _embed(_query: str, _settings: Settings) -> list[float]:
        raise RuntimeError("embedding unavailable")

    def _rerank(
        _query: str,
        candidates: list[RagCandidate],
        top_k: int,
        _settings: Settings,
    ) -> list[RagChunk]:
        return [
            RagChunk(
                candidate.doc_id,
                candidate.chunk_id,
                candidate.text,
                candidate.score,
                candidate.channel,
            )
            for candidate in candidates[:top_k]
        ]

    service = RagRetrievalService(
        store=Store(),
        embed_query=_embed,
        rerank=_rerank,
        settings=_settings(),
    )

    result = service.retrieve(
        RagQueryPlan(
            role_ids=("role-sales",),
            query="policy",
            top_k=3,
            prefetch_limit=3,
        )
    )

    assert result.dense_count == 0
    assert result.sparse_count == 1
    assert result.chunks[0].doc_id == "doc-a"
