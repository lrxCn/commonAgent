"""Qdrant-backed KB retrieval adapter."""

from __future__ import annotations

import logging
from collections.abc import Sequence

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


def roles_filter(role_ids: Sequence[str]) -> qmodels.Filter:
    """Intersection filter: payload ``role_ids[]`` meets user roles; M1 fallback ``role_id``."""
    ids = [rid.strip() for rid in role_ids if rid and str(rid).strip()]
    if not ids:
        return qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="role_id",
                    match=qmodels.MatchValue(value="__no_role__"),
                )
            ]
        )
    return qmodels.Filter(
        should=[
            qmodels.FieldCondition(
                key="role_ids",
                match=qmodels.MatchValue(value=rid),
            )
            for rid in ids
        ]
        + [
            qmodels.FieldCondition(
                key="role_id",
                match=qmodels.MatchValue(value=rid),
            )
            for rid in ids
        ]
    )


def role_filter(role_id: str) -> qmodels.Filter:
    """Single-role filter; prefer ``roles_filter`` for multi-role OR."""
    return roles_filter([role_id])


class QdrantKbStore:
    """Role-filtering Qdrant adapter for dense, text, and BM25 retrieval."""

    def __init__(self, *, client: QdrantClient, collection: str) -> None:
        self._client = client
        self._collection = collection

    def dense_search(
        self,
        *,
        role_ids: Sequence[str],
        query_vector: list[float],
        limit: int,
    ) -> list[RagCandidate]:
        role_filter_query = roles_filter(role_ids)
        try:
            hits = self._client.search(
                collection_name=self._collection,
                query_vector=(DENSE_VECTOR_NAME, query_vector),
                query_filter=role_filter_query,
                limit=limit,
                with_payload=True,
            )
        except Exception:
            try:
                hits = self._client.search(
                    collection_name=self._collection,
                    query_vector=query_vector,
                    query_filter=role_filter_query,
                    limit=limit,
                    with_payload=True,
                )
            except Exception:
                logger.debug("dense search failed for collection %s", self._collection, exc_info=True)
                return []

        candidates: list[RagCandidate] = []
        allowed = {rid.strip() for rid in role_ids if rid and str(rid).strip()}
        for hit in hits:
            item = hit_to_candidate(hit, channel="dense", role_ids=allowed or None)
            if item:
                candidates.append(item)
        return candidates

    def lexical_search(self, *, role_ids: Sequence[str], query: str, limit: int) -> list[RagCandidate]:
        if self._collection_has_sparse():
            logger.debug(
                "collection %s has sparse vectors; BM25 fallback used until sparse query vectors are wired",
                self._collection,
            )
        text_hits = self.text_search(role_ids=role_ids, query=query, limit=limit)
        bm25_hits = self.bm25_search(role_ids=role_ids, query=query, limit=limit)
        if text_hits and bm25_hits:
            return merge_candidates(text_hits, bm25_hits)[:limit]
        return bm25_hits or text_hits

    def text_search(self, *, role_ids: Sequence[str], query: str, limit: int) -> list[RagCandidate]:
        """Qdrant full-text scroll search, always role-scoped."""
        ids = [rid.strip() for rid in role_ids if rid and str(rid).strip()]
        if not query or not ids:
            return []
        scroll_filter = qmodels.Filter(
            must=[
                roles_filter(role_ids),
                qmodels.FieldCondition(
                    key="text",
                    match=qmodels.MatchText(text=query),
                ),
            ]
        )
        try:
            records, _ = self._client.scroll(
                collection_name=self._collection,
                scroll_filter=scroll_filter,
                limit=limit,
                with_payload=True,
            )
        except Exception:
            logger.debug("text scroll search failed", exc_info=True)
            return []

        allowed = set(ids)
        candidates: list[RagCandidate] = []
        for point in records:
            item = point_to_candidate(point, channel="text", score=0.5, role_ids=allowed)
            if item:
                candidates.append(item)
        return candidates

    def bm25_search(self, *, role_ids: Sequence[str], query: str, limit: int) -> list[RagCandidate]:
        """BM25 fallback over role-scoped payload text."""
        scroll_limit = max(BM25_MIN_SCROLL_LIMIT, limit * BM25_SCROLL_MULTIPLIER)
        try:
            records, _ = self._client.scroll(
                collection_name=self._collection,
                scroll_filter=roles_filter(role_ids),
                limit=scroll_limit,
                with_payload=True,
            )
        except Exception:
            logger.debug("BM25 role-scoped scroll failed", exc_info=True)
            return []

        allowed = {rid.strip() for rid in role_ids if rid and str(rid).strip()}
        candidates: list[RagCandidate] = []
        for point in records:
            item = point_to_candidate(point, channel="bm25", role_ids=allowed or None)
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
