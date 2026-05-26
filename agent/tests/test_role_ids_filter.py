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


def _field_matches(payload: dict[str, Any], cond: qmodels.FieldCondition) -> bool:
    key = cond.key
    value = cond.match.value if cond.match else None
    payload_val = payload.get(key)
    if isinstance(payload_val, list):
        return value in payload_val
    return payload_val == value


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
    assert len(flt.should) == 4
    keys = {cond.key for cond in flt.should}
    assert keys == {"role_ids", "role_id"}


def test_multi_role_document_hits_when_user_role_intersects() -> None:
    set_settings_override(_settings(QDRANT_MOCK=False, RERANK_TOP_K=5))

    def _raise_embed(_query: str) -> list[float]:
        raise RuntimeError("embedding unavailable")

    set_embed_query(_raise_embed)
    set_qdrant_client(  # type: ignore[arg-type]
        LexicalFakeQdrant(
            [
                {
                    "role_ids": ["role-sales", "role-support"],
                    "role_id": "role-sales",
                    "doc_id": "doc-multi",
                    "chunk_id": "chunk-multi",
                    "text": "多角色共享手册DELTA 销售与支持均可查看。",
                },
            ]
        )
    )

    chunks = retrieve(["role-support"], "多角色共享手册DELTA")
    assert [chunk.doc_id for chunk in chunks] == ["doc-multi"]


def test_multi_role_document_misses_without_intersection() -> None:
    set_settings_override(_settings(QDRANT_MOCK=False, RERANK_TOP_K=5))

    def _raise_embed(_query: str) -> list[float]:
        raise RuntimeError("embedding unavailable")

    set_embed_query(_raise_embed)
    set_qdrant_client(  # type: ignore[arg-type]
        LexicalFakeQdrant(
            [
                {
                    "role_ids": ["role-sales", "role-support"],
                    "role_id": "role-sales",
                    "doc_id": "doc-multi",
                    "chunk_id": "chunk-multi",
                    "text": "多角色共享手册DELTA 销售与支持均可查看。",
                },
            ]
        )
    )

    chunks = retrieve(["role-hr"], "多角色共享手册DELTA")
    assert chunks == []


def test_legacy_role_id_payload_still_retrievable() -> None:
    set_settings_override(_settings(QDRANT_MOCK=False, RERANK_TOP_K=5))

    def _raise_embed(_query: str) -> list[float]:
        raise RuntimeError("embedding unavailable")

    set_embed_query(_raise_embed)
    set_qdrant_client(  # type: ignore[arg-type]
        LexicalFakeQdrant(
            [
                {
                    "role_id": "role-hr",
                    "doc_id": "doc-legacy",
                    "chunk_id": "chunk-legacy",
                    "text": "旧版单角色年假政策DELTA。",
                },
            ]
        )
    )

    chunks = retrieve(["role-hr"], "年假政策DELTA")
    assert [chunk.doc_id for chunk in chunks] == ["doc-legacy"]
