#!/usr/bin/env python3
"""Run a local retrieval-only RAG eval over seed rows with kb_fixture."""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

_AGENT_DIR = Path(__file__).resolve().parent.parent
if str(_AGENT_DIR / "src") not in sys.path:
    sys.path.insert(0, str(_AGENT_DIR / "src"))

from qdrant_client.http import models as qmodels  # noqa: E402

from rag.ingest import ingest_document, reset_ingest_overrides, set_embed_texts  # noqa: E402
from rag.retriever import (  # noqa: E402
    reset_retriever_overrides,
    retrieve,
    set_embed_query,
    set_qdrant_client,
    set_reranker,
)
from settings.config import Settings, reset_settings, set_settings_override  # noqa: E402
from sync_langsmith_dataset import load_agent_env, load_seed  # noqa: E402

_DEFAULT_SEED = _AGENT_DIR / "evals" / "seed.json"
_REQUIRED_ENV = {
    "LANGSMITH_API_KEY": "lsv2_local_eval",
    "OPENAI_API_KEY": "sk-local-eval",
    "DATABASE_URL": "postgresql://postgres:local@localhost:5432/common_agent",
}


def _fake_embed(text: str) -> list[float]:
    vec = [0.0] * 1024
    for index, byte in enumerate(text.encode("utf-8")):
        vec[(byte + index * 31) % 1024] += 1.0
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec


def _fake_embed_batch(texts: Sequence[str]) -> list[list[float]]:
    return [_fake_embed(text) for text in texts]


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _matches_filter(payload: dict[str, Any], flt: qmodels.Filter | None) -> bool:
    if flt is None:
        return True
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
    if flt.must_not:
        for sub in flt.must_not:
            if isinstance(sub, qmodels.Filter) and _matches_filter(payload, sub):
                return False
    return True


class EvalQdrantClient:
    """In-memory Qdrant subset for deterministic retrieval evals."""

    def __init__(self) -> None:
        self.collections: set[str] = set()
        self.points: dict[str, dict[str, Any]] = {}

    def collection_exists(self, name: str) -> bool:
        return name in self.collections

    def create_collection(self, collection_name: str, vectors_config: object) -> None:
        self.collections.add(collection_name)

    def upsert(
        self,
        collection_name: str,
        points: list[qmodels.PointStruct],
        wait: bool = True,
    ) -> None:
        self.collections.add(collection_name)
        for point in points:
            self.points[str(point.id)] = {
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
            if row["collection"] == collection_name and _matches_filter(row["payload"], flt)
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
    ) -> list[Any]:
        if isinstance(query_vector, tuple):
            _, vector = query_vector
        else:
            vector = query_vector

        hits: list[tuple[float, dict[str, Any]]] = []
        for row in self.points.values():
            if row["collection"] != collection_name:
                continue
            payload = row["payload"]
            if query_filter and not _matches_filter(payload, query_filter):
                continue
            dense = row["vector"].get("dense") if isinstance(row["vector"], dict) else row["vector"]
            hits.append((_cosine(list(vector), list(dense)), payload))

        hits.sort(key=lambda item: item[0], reverse=True)
        return [
            _Hit(score=score, payload=payload, point_id=str(payload.get("chunk_id") or ""))
            for score, payload in hits[:limit]
        ]

    def scroll(
        self,
        collection_name: str,
        scroll_filter: qmodels.Filter | None = None,
        limit: int = 10,
        with_payload: bool = True,
    ) -> tuple[list[Any], None]:
        records: list[Any] = []
        for row in self.points.values():
            if row["collection"] != collection_name:
                continue
            payload = row["payload"]
            if scroll_filter and not _matches_filter(payload, scroll_filter):
                continue
            records.append(_Point(payload=payload, point_id=str(payload.get("chunk_id") or "")))
            if len(records) >= limit:
                break
        return records, None

    def get_collection(self, collection_name: str) -> Any:
        return _CollectionInfo()


class _Hit:
    def __init__(self, *, score: float, payload: dict[str, Any], point_id: str) -> None:
        self.score = score
        self.payload = payload
        self.id = point_id


class _Point:
    def __init__(self, *, payload: dict[str, Any], point_id: str) -> None:
        self.payload = payload
        self.id = point_id


class _CollectionInfo:
    class _Config:
        class _Params:
            sparse_vectors = None

        params = _Params()

    config = _Config()


def _settings() -> Settings:
    return Settings(
        **_REQUIRED_ENV,
        QDRANT_MOCK=False,
        QDRANT_COLLECTION_KB="kb_eval",
        RERANK_TOP_K=10,
    )


def _ingest_fixture(row: dict[str, Any]) -> None:
    fixture = row.get("kb_fixture")
    if not isinstance(fixture, list):
        return
    for doc in fixture:
        if not isinstance(doc, dict):
            continue
        ingest_document(
            role_id=str(doc["role_id"]),
            doc_id=str(doc["doc_id"]),
            doc_name=str(doc["doc_name"]),
            version=str(doc.get("version") or "eval"),
            content=str(doc["content"]),
        )


def evaluate_rows(rows: list[dict[str, Any]], *, top_k: int) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for row in rows:
        expected = row.get("expected_answer") or {}
        if not isinstance(expected, dict) or not expected.get("requires_rag"):
            continue
        client = EvalQdrantClient()
        set_qdrant_client(client)  # type: ignore[arg-type]
        _ingest_fixture(row)
        context = row.get("context") or {}
        role_id = str(context.get("role_id") or "")
        chunks = retrieve(role_id, str(row["input"]), top_k=top_k)
        returned_doc_ids = [chunk.doc_id for chunk in chunks]
        expected_doc_ids = list(expected.get("expected_doc_ids") or [])
        forbidden_doc_ids = list(expected.get("forbidden_doc_ids") or [])
        hit = bool(expected_doc_ids) and any(doc_id in returned_doc_ids for doc_id in expected_doc_ids)
        forbidden_hit = any(doc_id in returned_doc_ids for doc_id in forbidden_doc_ids)
        results.append(
            {
                "id": row["id"],
                "hit": hit,
                "forbidden_hit": forbidden_hit,
                "returned_doc_ids": returned_doc_ids,
                "expected_doc_ids": expected_doc_ids,
                "forbidden_doc_ids": forbidden_doc_ids,
            }
        )
    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=Path, default=_DEFAULT_SEED)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_agent_env()
    rows = load_seed(args.seed)
    reset_settings()
    reset_ingest_overrides()
    reset_retriever_overrides()
    set_settings_override(_settings())
    set_embed_texts(_fake_embed_batch)
    set_embed_query(_fake_embed)
    set_reranker(lambda _q, docs: [float(len(docs) - index) for index, _ in enumerate(docs)])

    results = evaluate_rows(rows, top_k=max(1, int(args.top_k)))
    passed = sum(1 for item in results if item["hit"] and not item["forbidden_hit"])
    summary = {
        "rows": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "results": results,
    }
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"rag_eval rows={summary['rows']} passed={summary['passed']} failed={summary['failed']}")
        for item in results:
            status = "pass" if item["hit"] and not item["forbidden_hit"] else "fail"
            print(f"{status}: {item['id']} returned={item['returned_doc_ids']}")
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
