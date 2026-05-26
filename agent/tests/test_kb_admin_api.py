"""Tests for KB document list/get/delete — mocked Qdrant."""

from __future__ import annotations

import math
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from qdrant_client.http import models as qmodels

from gateway.app import create_app
from rag.ingest import ingest_document, reset_ingest_overrides, set_embed_texts
from rag.kb_documents import KbDocumentError, delete_document, get_document, list_documents
from rag.retriever import reset_retriever_overrides, set_embed_query, set_qdrant_client
from settings.config import Settings, reset_settings, set_settings_override

_REQUIRED_ENV = {
    "LANGSMITH_API_KEY": "lsv2_test",
    "OPENAI_API_KEY": "sk-test",
    "DATABASE_URL": "postgresql://postgres:test@localhost:5432/common_agent",
}


def _settings(**extra: object) -> Settings:
    return Settings(**{**_REQUIRED_ENV, **extra})  # type: ignore[arg-type]


def _fake_embed(text: str) -> list[float]:
    vec = [0.0] * 1024
    for index, ch in enumerate(text.encode("utf-8")):
        vec[(ch + index * 31) % 1024] += 1.0
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec


def _fake_embed_batch(texts: list[str]) -> list[list[float]]:
    return [_fake_embed(t) for t in texts]


def _field_matches(payload: dict[str, Any], cond: qmodels.FieldCondition) -> bool:
    key = cond.key
    value = cond.match.value if cond.match else None
    return payload.get(key) == value


def _payload_matches_filter(payload: dict[str, Any], flt: qmodels.Filter | None) -> bool:
    if flt is None:
        return True
    if flt.must:
        for cond in flt.must:
            if not _field_matches(payload, cond):
                return False
    if flt.should:
        if not any(_field_matches(payload, cond) for cond in flt.should):
            return False
    if flt.must_not:
        for sub in flt.must_not:
            if isinstance(sub, qmodels.Filter) and _payload_matches_filter(payload, sub):
                return False
    return True


class FakeQdrantClient:
    """Minimal in-memory Qdrant for KB admin tests."""

    def __init__(self) -> None:
        self.points: dict[str, dict[str, Any]] = {}
        self.collections: set[str] = set()

    def collection_exists(self, name: str) -> bool:
        return name in self.collections

    def create_collection(
        self,
        collection_name: str,
        vectors_config: object,
    ) -> None:
        self.collections.add(collection_name)

    def upsert(
        self,
        collection_name: str,
        points: list[qmodels.PointStruct],
        wait: bool = True,
    ) -> None:
        self.collections.add(collection_name)
        for point in points:
            pid = str(point.id)
            self.points[pid] = {
                "collection": collection_name,
                "vector": dict(point.vector) if isinstance(point.vector, dict) else point.vector,
                "payload": dict(point.payload or {}),
            }

    def delete(
        self,
        collection_name: str,
        points_selector: qmodels.FilterSelector,
        wait: bool = True,
    ) -> None:
        flt = points_selector.filter
        to_remove = [
            pid
            for pid, row in self.points.items()
            if row["collection"] == collection_name
            and _payload_matches_filter(row["payload"], flt)
        ]
        for pid in to_remove:
            del self.points[pid]

    def scroll(
        self,
        collection_name: str,
        scroll_filter: qmodels.Filter | None = None,
        limit: int = 10,
        offset: object = None,
        with_payload: bool = True,
    ) -> tuple[list[MagicMock], None]:
        del offset
        records: list[MagicMock] = []
        for row in self.points.values():
            if row["collection"] != collection_name:
                continue
            if scroll_filter and not _payload_matches_filter(row["payload"], scroll_filter):
                continue
            point = MagicMock()
            point.payload = row["payload"]
            point.id = row["payload"].get("chunk_id")
            records.append(point)
            if len(records) >= limit:
                break
        return records, None


@pytest.fixture(autouse=True)
def _clean() -> None:
    reset_ingest_overrides()
    reset_retriever_overrides()
    reset_settings()
    yield
    reset_ingest_overrides()
    reset_retriever_overrides()
    reset_settings()


@pytest.fixture
def fake_qdrant() -> FakeQdrantClient:
    client = FakeQdrantClient()
    set_qdrant_client(client)  # type: ignore[arg-type]
    set_embed_texts(_fake_embed_batch)
    set_embed_query(_fake_embed)
    return client


def _seed_doc(
    fake_qdrant: FakeQdrantClient,
    *,
    role_id: str,
    doc_id: str,
    doc_name: str,
    version: str,
    content: str,
) -> None:
    set_settings_override(
        _settings(QDRANT_MOCK=False, QDRANT_COLLECTION_KB="kb_admin_test")
    )
    ingest_document(
        role_id=role_id,
        doc_id=doc_id,
        doc_name=doc_name,
        version=version,
        content=content,
    )
    assert fake_qdrant.points


def test_list_documents_groups_by_doc_and_role(fake_qdrant: FakeQdrantClient) -> None:
    _seed_doc(
        fake_qdrant,
        role_id="role-sales",
        doc_id="doc-a",
        doc_name="手册A",
        version="1",
        content="销售条款一。销售条款二。",
    )
    _seed_doc(
        fake_qdrant,
        role_id="role-hr",
        doc_id="doc-b",
        doc_name="手册B",
        version="1",
        content="人事制度说明。",
    )

    sales_items = list_documents(["role-sales"])
    assert len(sales_items) == 1
    assert sales_items[0].doc_id == "doc-a"
    assert sales_items[0].chunks_written >= 1

    both = list_documents(["role-sales", "role-hr"])
    assert len(both) == 2
    assert {item.doc_id for item in both} == {"doc-a", "doc-b"}


def test_get_document_returns_chunk_previews(fake_qdrant: FakeQdrantClient) -> None:
    marker = "chunk预览MARKER"
    _seed_doc(
        fake_qdrant,
        role_id="role-sales",
        doc_id="doc-preview",
        doc_name="预览文档",
        version="v1",
        content=f"第一段：{marker}。第二段补充。",
    )

    detail = get_document("doc-preview", "role-sales")
    assert detail.doc_name == "预览文档"
    assert detail.chunks_written >= 1
    assert any(marker in chunk.text for chunk in detail.chunks)


def test_get_document_missing_raises(fake_qdrant: FakeQdrantClient) -> None:
    set_settings_override(
        _settings(QDRANT_MOCK=False, QDRANT_COLLECTION_KB="kb_admin_test")
    )
    with pytest.raises(KbDocumentError, match="not found"):
        get_document("missing-doc", "role-sales")


def test_delete_document_removes_points(fake_qdrant: FakeQdrantClient) -> None:
    _seed_doc(
        fake_qdrant,
        role_id="role-sales",
        doc_id="doc-del",
        doc_name="待删文档",
        version="1",
        content="删除测试内容。",
    )
    assert list_documents(["role-sales"])

    delete_document("doc-del", "role-sales")
    assert list_documents(["role-sales"]) == []


def test_gateway_list_requires_role_id() -> None:
    set_settings_override(_settings())
    client = TestClient(create_app())
    response = client.get("/internal/kb/documents")
    assert response.status_code == 422


def test_gateway_kb_crud_endpoints(fake_qdrant: FakeQdrantClient) -> None:
    set_settings_override(
        _settings(QDRANT_MOCK=False, QDRANT_COLLECTION_KB="kb_admin_test")
    )
    client = TestClient(create_app())

    ingest = client.post(
        "/internal/kb/ingest",
        json={
            "role_id": "role-sales",
            "doc_id": "doc-api",
            "doc_name": "API文档",
            "version": "1",
            "content": "网关测试正文。",
        },
    )
    assert ingest.status_code == 200

    listed = client.get("/internal/kb/documents", params={"role_id": "role-sales"})
    assert listed.status_code == 200
    items = listed.json()["items"]
    assert any(item["doc_id"] == "doc-api" for item in items)

    detail = client.get(
        "/internal/kb/documents/doc-api",
        params={"role_id": "role-sales"},
    )
    assert detail.status_code == 200
    assert detail.json()["chunks_written"] >= 1

    deleted = client.delete(
        "/internal/kb/documents/doc-api",
        params={"role_id": "role-sales"},
    )
    assert deleted.status_code == 204

    listed_after = client.get("/internal/kb/documents", params={"role_id": "role-sales"})
    assert listed_after.json()["items"] == []
