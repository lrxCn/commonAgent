"""Qdrant-backed KB retrieval adapter."""

from __future__ import annotations

import logging

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from domain.rag.lexical.bm25 import BM25_MIN_SCROLL_LIMIT, BM25_SCROLL_MULTIPLIER, score_bm25
from domain.rag.merge import merge_candidates
from domain.rag.models import RagCandidate
from infrastructure.qdrant.payload import hit_to_candidate, point_to_candidate
from settings.config import Settings

logger = logging.getLogger(__name__)

DENSE_VECTOR_NAME = "dense"
_qdrant_client_override: QdrantClient | None = None


def set_qdrant_client_override(client: QdrantClient | None) -> None:
    """Override Qdrant client for tests across retrieval and ingest."""
    global _qdrant_client_override
    _qdrant_client_override = client


def get_qdrant_client(settings: Settings) -> QdrantClient:
    if _qdrant_client_override is not None:
        return _qdrant_client_override
    return QdrantClient(url=settings.qdrant_url, prefer_grpc=False)


def role_filter(role_id: str) -> qmodels.Filter:
    return qmodels.Filter(
        must=[
            qmodels.FieldCondition(
                key="role_id",
                match=qmodels.MatchValue(value=role_id),
            )
        ]
    )


class QdrantKbStore:
    """Role-filtering Qdrant adapter for dense, text, and BM25 retrieval."""

    def __init__(self, *, client: QdrantClient, collection: str) -> None:
        self._client = client
        self._collection = collection

    def dense_search(
        self,
        *,
        role_id: str,
        query_vector: list[float],
        limit: int,
    ) -> list[RagCandidate]:
        try:
            hits = self._client.search(
                collection_name=self._collection,
                query_vector=(DENSE_VECTOR_NAME, query_vector),
                query_filter=role_filter(role_id),
                limit=limit,
                with_payload=True,
            )
        except Exception:
            try:
                hits = self._client.search(
                    collection_name=self._collection,
                    query_vector=query_vector,
                    query_filter=role_filter(role_id),
                    limit=limit,
                    with_payload=True,
                )
            except Exception:
                logger.debug("dense search failed for collection %s", self._collection, exc_info=True)
                return []

        candidates: list[RagCandidate] = []
        for hit in hits:
            item = hit_to_candidate(hit, channel="dense", role_id=role_id)
            if item:
                candidates.append(item)
        return candidates

    def lexical_search(self, *, role_id: str, query: str, limit: int) -> list[RagCandidate]:
        if self._collection_has_sparse():
            logger.debug(
                "collection %s has sparse vectors; BM25 fallback used until sparse query vectors are wired",
                self._collection,
            )
        text_hits = self.text_search(role_id=role_id, query=query, limit=limit)
        bm25_hits = self.bm25_search(role_id=role_id, query=query, limit=limit)
        if text_hits and bm25_hits:
            return merge_candidates(text_hits, bm25_hits)[:limit]
        return bm25_hits or text_hits

    def text_search(self, *, role_id: str, query: str, limit: int) -> list[RagCandidate]:
        """Qdrant full-text scroll search, always role-scoped."""
        if not query:
            return []
        try:
            records, _ = self._client.scroll(
                collection_name=self._collection,
                scroll_filter=qmodels.Filter(
                    must=[
                        qmodels.FieldCondition(
                            key="role_id",
                            match=qmodels.MatchValue(value=role_id),
                        ),
                        qmodels.FieldCondition(
                            key="text",
                            match=qmodels.MatchText(text=query),
                        ),
                    ]
                ),
                limit=limit,
                with_payload=True,
            )
        except Exception:
            logger.debug("text scroll search failed", exc_info=True)
            return []

        candidates: list[RagCandidate] = []
        for point in records:
            item = point_to_candidate(point, channel="text", score=0.5, role_id=role_id)
            if item:
                candidates.append(item)
        return candidates

    def bm25_search(self, *, role_id: str, query: str, limit: int) -> list[RagCandidate]:
        """BM25 fallback over role-scoped payload text."""
        scroll_limit = max(BM25_MIN_SCROLL_LIMIT, limit * BM25_SCROLL_MULTIPLIER)
        try:
            records, _ = self._client.scroll(
                collection_name=self._collection,
                scroll_filter=role_filter(role_id),
                limit=scroll_limit,
                with_payload=True,
            )
        except Exception:
            logger.debug("BM25 role-scoped scroll failed", exc_info=True)
            return []

        candidates: list[RagCandidate] = []
        for point in records:
            item = point_to_candidate(point, channel="bm25", role_id=role_id)
            if item:
                candidates.append(item)
        return score_bm25(query, candidates, limit=limit)

    def _collection_has_sparse(self) -> bool:
        try:
            info = self._client.get_collection(self._collection)
            config = info.config.params if info.config else None  # type: ignore[union-attr]
            if config is None:
                return False
            sparse_vectors = getattr(config, "sparse_vectors", None)
            return bool(sparse_vectors)
        except Exception:
            return False
