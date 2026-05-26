"""Role-scoped RAG isolation and multi-role OR retrieval."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from qdrant_client.http import models as qmodels

from gateway.schemas import RequestContext
from infrastructure.qdrant.kb_store import roles_filter
from rag.retriever import (
    reset_retriever_overrides,
    retrieve,
    set_embed_query,
    set_qdrant_client,
)
from settings.config import Settings, reset_settings, set_settings_override

_REQUIRED_ENV = {
    "LANGSMITH_API_KEY": "lsv2_test",
    "OPENAI_API_KEY": "sk-test",
    "DATABASE_URL": "postgresql://postgres:test@localhost:5432/common_agent",
}


@pytest.fixture(autouse=True)
def _clean() -> None:
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
    return True


class LexicalFakeQdrant:
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


def test_request_context_accepts_role_ids() -> None:
    ctx = RequestContext.model_validate(
        {"user_id": "u1", "role_ids": ["role-sales", "role-support"]}
    )
    assert ctx.role_ids == ["role-sales", "role-support"]


def test_request_context_deprecated_role_id_alias() -> None:
    ctx = RequestContext.model_validate({"user_id": "u1", "role_id": "role-sales"})
    assert ctx.role_ids == ["role-sales"]
    assert ctx.role_id == "role-sales"


def test_request_context_deduplicates_role_ids() -> None:
    ctx = RequestContext.model_validate(
        {"user_id": "u1", "role_ids": ["role-sales", "role-sales", " role-hr "]}
    )
    assert ctx.role_ids == ["role-sales", "role-hr"]


def test_single_role_isolation_matches_legacy_behavior() -> None:
    set_settings_override(_settings(QDRANT_MOCK=True, RERANK_TOP_K=10))
    sales = retrieve("role-sales", "制度")
    hr = retrieve("role-hr", "制度")
    assert all(chunk.doc_id == "doc-reimbursement" for chunk in sales)
    assert all(chunk.doc_id == "doc-leave" for chunk in hr)
    assert "doc-leave" not in {chunk.doc_id for chunk in sales}
    assert "doc-reimbursement" not in {chunk.doc_id for chunk in hr}


def test_multi_role_or_retrieval_mock() -> None:
    set_settings_override(_settings(QDRANT_MOCK=True, RERANK_TOP_K=10))
    chunks = retrieve(["role-sales", "role-hr"], "制度")
    doc_ids = {chunk.doc_id for chunk in chunks}
    assert doc_ids == {"doc-reimbursement", "doc-leave"}


def test_multi_role_or_retrieval_unions_distinct_roles() -> None:
    set_settings_override(_settings(QDRANT_MOCK=True, RERANK_TOP_K=10))
    chunks = retrieve(["role-sales", "role-hr"], "制度")
    doc_ids = {chunk.doc_id for chunk in chunks}
    assert doc_ids == {"doc-reimbursement", "doc-leave"}


def test_cross_role_leakage_blocked_with_or_filter() -> None:
    set_settings_override(_settings(QDRANT_MOCK=False, RERANK_TOP_K=5))

    def _raise_embed(_query: str) -> list[float]:
        raise RuntimeError("embedding unavailable")

    set_embed_query(_raise_embed)
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

    chunks = retrieve(["role-hr"], "内部返点策略DELTA")
    assert not any(chunk.doc_id == "doc-sales-secret" for chunk in chunks)
    assert [chunk.doc_id for chunk in chunks] == ["doc-hr-public"]


def test_roles_filter_uses_qdrant_should_for_multiple_roles() -> None:
    flt = roles_filter(["role-sales", "role-hr"])
    assert flt.should is not None
    assert len(flt.should) == 2
