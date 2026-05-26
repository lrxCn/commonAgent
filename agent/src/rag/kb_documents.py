"""KB document list/get/delete against Qdrant (vectors only; raw text lives in Back meta)."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from settings.config import Settings, get_settings

from infrastructure.qdrant.kb_store import get_qdrant_client, roles_filter

logger = logging.getLogger(__name__)


class KbDocumentError(Exception):
    """Raised when a KB document operation cannot complete."""


@dataclass(frozen=True)
class KbDocumentSummary:
    doc_id: str
    doc_name: str
    version: str
    role_ids: list[str]
    chunks_written: int


@dataclass(frozen=True)
class KbChunkPreview:
    chunk_id: str
    index: int
    text: str


@dataclass(frozen=True)
class KbDocumentDetail:
    doc_id: str
    doc_name: str
    version: str
    role_ids: list[str]
    chunks_written: int
    chunks: list[KbChunkPreview]


def _normalize_query_role_ids(role_ids: Sequence[str]) -> list[str]:
    ids = [rid.strip() for rid in role_ids if rid and str(rid).strip()]
    if not ids:
        msg = "role_id is required"
        raise KbDocumentError(msg)
    return ids


def _payload_role_ids(payload: dict[str, object]) -> list[str]:
    raw = payload.get("role_ids")
    if isinstance(raw, list):
        normalized = _normalize_role_ids_from_payload(raw)
        if normalized:
            return normalized
    legacy = payload.get("role_id")
    if legacy and str(legacy).strip():
        return [str(legacy).strip()]
    return []


def _normalize_role_ids_from_payload(role_ids: Sequence[object]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in role_ids:
        role_id = str(raw).strip()
        if not role_id or role_id in seen:
            continue
        seen.add(role_id)
        normalized.append(role_id)
    return normalized


def _doc_id_filter(doc_id: str) -> qmodels.Filter:
    return qmodels.Filter(
        must=[
            qmodels.FieldCondition(
                key="doc_id",
                match=qmodels.MatchValue(value=doc_id.strip()),
            )
        ]
    )


def _scroll_points(
    client: QdrantClient,
    *,
    collection: str,
    scroll_filter: qmodels.Filter,
    limit: int = 10_000,
) -> list[qmodels.Record]:
    records: list[qmodels.Record] = []
    offset = None
    while True:
        batch, offset = client.scroll(
            collection_name=collection,
            scroll_filter=scroll_filter,
            limit=min(limit, 256),
            offset=offset,
            with_payload=True,
        )
        records.extend(batch)
        if offset is None or len(records) >= limit:
            break
    return records


def list_documents(
    role_ids: Sequence[str],
    *,
    settings: Settings | None = None,
) -> list[KbDocumentSummary]:
    """List unique documents whose payload role_ids intersect the query roles."""
    cfg = settings or get_settings()
    query_ids = set(_normalize_query_role_ids(role_ids))
    client = get_qdrant_client(cfg)
    collection = cfg.QDRANT_COLLECTION_KB

    if not client.collection_exists(collection):
        return []

    try:
        records = _scroll_points(
            client,
            collection=collection,
            scroll_filter=roles_filter(role_ids),
        )
    except Exception as exc:
        msg = "failed to list kb documents"
        raise KbDocumentError(msg) from exc

    grouped: dict[str, dict[str, object]] = {}
    for record in records:
        payload = record.payload or {}
        doc_id = str(payload.get("doc_id") or "").strip()
        payload_roles = _payload_role_ids(payload)
        if not doc_id or not payload_roles:
            continue
        if not query_ids.intersection(payload_roles):
            continue
        row = grouped.setdefault(
            doc_id,
            {
                "doc_name": str(payload.get("doc_name") or doc_id),
                "version": str(payload.get("version") or "1"),
                "role_ids": payload_roles,
                "chunks_written": 0,
            },
        )
        row["chunks_written"] = int(row["chunks_written"]) + 1
        row["doc_name"] = str(payload.get("doc_name") or row["doc_name"])
        row["version"] = str(payload.get("version") or row["version"])
        row["role_ids"] = payload_roles

    summaries = [
        KbDocumentSummary(
            doc_id=doc_id,
            doc_name=str(row["doc_name"]),
            version=str(row["version"]),
            role_ids=list(row["role_ids"]),  # type: ignore[arg-type]
            chunks_written=int(row["chunks_written"]),
        )
        for doc_id, row in grouped.items()
    ]
    summaries.sort(key=lambda item: (item.doc_name, item.doc_id))
    return summaries


def get_document(
    doc_id: str,
    *,
    settings: Settings | None = None,
) -> KbDocumentDetail:
    """Return chunk previews for a document (not full raw_content)."""
    cfg = settings or get_settings()
    did = doc_id.strip()
    if not did:
        msg = "doc_id is required"
        raise KbDocumentError(msg)

    client = get_qdrant_client(cfg)
    collection = cfg.QDRANT_COLLECTION_KB
    if not client.collection_exists(collection):
        msg = f"document not found: {did}"
        raise KbDocumentError(msg)

    try:
        records = _scroll_points(
            client,
            collection=collection,
            scroll_filter=_doc_id_filter(did),
        )
    except Exception as exc:
        msg = "failed to load kb document"
        raise KbDocumentError(msg) from exc

    if not records:
        msg = f"document not found: {did}"
        raise KbDocumentError(msg)

    first = records[0].payload or {}
    doc_name = str(first.get("doc_name") or did)
    version = str(first.get("version") or "1")
    role_ids = _payload_role_ids(first)

    chunks: list[KbChunkPreview] = []
    for record in records:
        payload = record.payload or {}
        chunk_id = str(payload.get("chunk_id") or record.id)
        text = str(payload.get("text") or "")
        index = _chunk_index(chunk_id)
        chunks.append(KbChunkPreview(chunk_id=chunk_id, index=index, text=text))
    chunks.sort(key=lambda item: item.index)

    return KbDocumentDetail(
        doc_id=did,
        doc_name=doc_name,
        version=version,
        role_ids=role_ids,
        chunks_written=len(chunks),
        chunks=chunks,
    )


def _chunk_index(chunk_id: str) -> int:
    if ":" not in chunk_id:
        return 0
    tail = chunk_id.rsplit(":", 1)[-1]
    try:
        return int(tail)
    except ValueError:
        return 0


def delete_document(
    doc_id: str,
    *,
    settings: Settings | None = None,
) -> None:
    """Delete all Qdrant points for doc_id."""
    cfg = settings or get_settings()
    did = doc_id.strip()
    if not did:
        msg = "doc_id is required"
        raise KbDocumentError(msg)

    client = get_qdrant_client(cfg)
    collection = cfg.QDRANT_COLLECTION_KB
    if not client.collection_exists(collection):
        return

    try:
        client.delete(
            collection_name=collection,
            points_selector=qmodels.FilterSelector(
                filter=_doc_id_filter(did),
            ),
            wait=True,
        )
    except Exception as exc:
        msg = "failed to delete kb document"
        raise KbDocumentError(msg) from exc

    logger.info("deleted kb doc_id=%s", did)
