"""Tests for KB ingest — mocked Qdrant; no live embedding or Qdrant server."""

from __future__ import annotations

import math
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from qdrant_client.http import models as qmodels

from gateway.app import create_app
from rag.ingest import (
    IngestError,
    chunk_text,
    effective_chunk_size_tokens,
    estimate_tokens,
    ingest_document,
    reset_ingest_overrides,
    set_embed_texts,
)
from rag.retriever import reset_retriever_overrides, retrieve, set_embed_query, set_qdrant_client
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


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _payload_matches_filter(payload: dict[str, Any], flt: qmodels.Filter | None) -> bool:
    if flt is None:
        return True
    if flt.must:
        for cond in flt.must:
            key = cond.key
            value = cond.match.value if cond.match else None
            if payload.get(key) != value:
                return False
    if flt.must_not:
        for sub in flt.must_not:
            if isinstance(sub, qmodels.Filter) and _payload_matches_filter(payload, sub):
                return False
    return True


class FakeQdrantClient:
    """Minimal in-memory Qdrant for ingest + dense search tests."""

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

    def search(
        self,
        collection_name: str,
        query_vector: object,
        query_filter: qmodels.Filter | None = None,
        limit: int = 10,
        with_payload: bool = True,
    ) -> list[MagicMock]:
        if isinstance(query_vector, tuple):
            _, vector = query_vector
        else:
            vector = query_vector

        hits: list[tuple[float, dict[str, Any]]] = []
        for row in self.points.values():
            if row["collection"] != collection_name:
                continue
            payload = row["payload"]
            if query_filter and not _payload_matches_filter(payload, query_filter):
                continue
            dense = row["vector"].get("dense") if isinstance(row["vector"], dict) else row["vector"]
            score = _cosine(list(vector), list(dense))
            hits.append((score, payload))

        hits.sort(key=lambda item: item[0], reverse=True)
        results: list[MagicMock] = []
        for score, payload in hits[:limit]:
            hit = MagicMock()
            hit.score = score
            hit.id = payload.get("chunk_id")
            hit.payload = payload
            results.append(hit)
        return results

    def scroll(
        self,
        collection_name: str,
        scroll_filter: qmodels.Filter | None = None,
        limit: int = 10,
        with_payload: bool = True,
    ) -> tuple[list[MagicMock], None]:
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

    def get_collection(self, collection_name: str) -> MagicMock:
        return MagicMock(
            config=MagicMock(params=MagicMock(sparse_vectors=None))
        )


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


def test_chunk_text_respects_size_and_overlap() -> None:
    text = "第一句。" * 200
    chunks = chunk_text(text, chunk_size_tokens=64, overlap_ratio=0.12)
    assert len(chunks) >= 2
    for chunk in chunks:
        assert estimate_tokens(chunk) <= 128


def test_effective_chunk_size_tokens_respects_embedding_limit() -> None:
    settings = _settings(
        CHUNK_SIZE_TOKENS=768,
        EMBEDDING_MAX_INPUT_TOKENS=512,
    )
    assert effective_chunk_size_tokens(settings) == 480


def test_ingest_then_retrieve_hits_content(fake_qdrant: FakeQdrantClient) -> None:
    set_settings_override(
        _settings(QDRANT_MOCK=False, QDRANT_COLLECTION_KB="kb_test")
    )
    unique = "报销制度专项条款ALPHA"
    ingest_document(
        role_id="role-sales",
        doc_id="doc-alpha",
        doc_name="报销手册",
        version="v1",
        content=f"公司规定：{unique} 需在30日内提交。",
    )
    chunks = retrieve("role-sales", unique)
    assert chunks
    assert any(unique in c.text for c in chunks)
    assert chunks[0].doc_id == "doc-alpha"


def test_reingest_same_doc_name_removes_old_version(fake_qdrant: FakeQdrantClient) -> None:
    set_settings_override(
        _settings(QDRANT_MOCK=False, QDRANT_COLLECTION_KB="kb_test")
    )
    old_marker = "旧版条款OMEGA"
    new_marker = "新版条款SIGMA"
    ingest_document(
        role_id="role-sales",
        doc_id="doc-policy",
        doc_name="政策文件",
        version="v1",
        content=f"内容：{old_marker}",
    )
    ingest_document(
        role_id="role-sales",
        doc_id="doc-policy",
        doc_name="政策文件",
        version="v2",
        content=f"内容：{new_marker}",
    )
    old_hits = retrieve("role-sales", old_marker)
    new_hits = retrieve("role-sales", new_marker)
    assert not any(old_marker in c.text for c in old_hits)
    assert new_hits
    assert all(new_marker in c.text for c in new_hits)


def test_ingest_empty_content_raises() -> None:
    set_settings_override(_settings(QDRANT_MOCK=False))
    with pytest.raises(IngestError, match="empty"):
        ingest_document(
            role_id="role-sales",
            doc_id="d1",
            doc_name="n1",
            version="v1",
            content="   ",
        )


def test_gateway_ingest_endpoint(fake_qdrant: FakeQdrantClient) -> None:
    set_settings_override(
        _settings(QDRANT_MOCK=False, AGENT_PORT=18080)
    )
    client = TestClient(create_app())
    response = client.post(
        "/internal/kb/ingest",
        json={
            "role_id": "role-hr",
            "doc_id": "doc-leave",
            "doc_name": "年假制度",
            "version": "2026-05",
            "content": "年假规则：工作满一年享有5天带薪年假。",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["doc_id"] == "doc-leave"
    assert body["chunks_written"] >= 1
    assert body["tokens_estimated"] > 0


def test_gateway_rejects_missing_content_and_file() -> None:
    set_settings_override(_settings())
    client = TestClient(create_app())
    response = client.post(
        "/internal/kb/ingest",
        json={
            "role_id": "role-hr",
            "doc_id": "d1",
            "doc_name": "n1",
            "version": "v1",
        },
    )
    assert response.status_code == 422
