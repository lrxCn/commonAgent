"""Knowledge-base ingest: chunk, embed, upsert to Qdrant, prune by doc_name."""

from __future__ import annotations

import logging
import re
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from settings.config import Settings, get_settings

from infrastructure.llm.gateway import get_llm_gateway
from infrastructure.qdrant.kb_store import DENSE_VECTOR_NAME, get_qdrant_client

logger = logging.getLogger(__name__)

_embed_texts_override: Callable[[Sequence[str]], list[list[float]]] | None = None

# Split on sentence / paragraph boundaries (Chinese + Western punctuation).
_SPLIT_RE = re.compile(r"(?<=[。！？；\n.!?;])\s*")


@dataclass(frozen=True)
class IngestResult:
    """Outcome of a single document ingest."""

    doc_id: str
    doc_name: str
    version: str
    chunks_written: int
    tokens_estimated: int


class IngestError(Exception):
    """Raised when ingest cannot complete (validation, I/O, Qdrant)."""


def set_embed_texts(fn: Callable[[Sequence[str]], list[list[float]]] | None) -> None:
    """Replace batch embedding (tests). Pass None to clear."""
    global _embed_texts_override
    _embed_texts_override = fn


def reset_ingest_overrides() -> None:
    """Clear ingest test overrides."""
    set_embed_texts(None)


def estimate_tokens(text: str) -> int:
    """Rough token count for chunk sizing (no extra tokenizer dependency)."""
    stripped = text.strip()
    if not stripped:
        return 0
    cjk = sum(1 for ch in stripped if "\u4e00" <= ch <= "\u9fff")
    other = len(stripped) - cjk
    return max(1, cjk + (other + 3) // 4)


def chunk_text(
    text: str,
    *,
    chunk_size_tokens: int,
    overlap_ratio: float,
) -> list[str]:
    """
    Split ``text`` into chunks of roughly ``chunk_size_tokens`` with overlap.

    Overlap ratio follows the root README target range when configured out of range
    only for the configured setting — callers pass settings-validated values.
    """
    body = text.strip()
    if not body:
        return []

    size = max(64, chunk_size_tokens)
    overlap = max(0, int(size * overlap_ratio))
    step = max(1, size - overlap)

    units = [u.strip() for u in _SPLIT_RE.split(body) if u.strip()]
    if not units:
        units = [body]

    chunks: list[str] = []
    buffer: list[str] = []
    buffer_tokens = 0

    def flush_buffer() -> None:
        nonlocal buffer, buffer_tokens
        if not buffer:
            return
        chunk = "".join(buffer).strip()
        if chunk:
            chunks.append(chunk)
        buffer = []
        buffer_tokens = 0

    def carry_overlap() -> None:
        nonlocal buffer, buffer_tokens
        if overlap <= 0 or not buffer:
            buffer = []
            buffer_tokens = 0
            return
        tail: list[str] = []
        tail_tokens = 0
        for unit in reversed(buffer):
            tail.insert(0, unit)
            tail_tokens += estimate_tokens(unit)
            if tail_tokens >= overlap:
                break
        buffer = tail
        buffer_tokens = tail_tokens

    for unit in units:
        unit_tokens = estimate_tokens(unit)
        if unit_tokens >= size and not buffer:
            chars = list(unit)
            start = 0
            while start < len(chars):
                end = min(len(chars), start + size * 2)
                piece = "".join(chars[start:end]).strip()
                if piece:
                    chunks.append(piece)
                if end >= len(chars):
                    break
                start += step * 2
            continue

        if buffer_tokens + unit_tokens > size and buffer:
            flush_buffer()
            carry_overlap()

        buffer.append(unit)
        buffer_tokens += unit_tokens

    flush_buffer()
    return chunks or [body]


def effective_chunk_size_tokens(settings: Settings) -> int:
    """Cap ingest chunk size so each embedding input stays under provider limits."""
    target = max(64, settings.CHUNK_SIZE_TOKENS)
    provider_limit = max(64, settings.EMBEDDING_MAX_INPUT_TOKENS)
    # Heuristic token counts can exceed the provider tokenizer; keep a safety margin.
    safety_margin = 32
    capped = max(64, provider_limit - safety_margin)
    return min(target, capped)


def _embed_texts(texts: Sequence[str], settings: Settings) -> list[list[float]]:
    if not texts:
        return []
    if _embed_texts_override is not None:
        return _embed_texts_override(texts)

    return get_llm_gateway(settings).embed_documents(texts)


def _read_content(*, content: str | None, file_path: str | None) -> str:
    if content is not None:
        stripped = content.strip()
        if stripped:
            return stripped
        if file_path is None or not str(file_path).strip():
            msg = "document content is empty"
            raise IngestError(msg)
    if file_path is None or not str(file_path).strip():
        msg = "content or file_path is required"
        raise IngestError(msg)
    path = Path(file_path).expanduser()
    if not path.is_file():
        msg = f"file_path not found: {file_path}"
        raise IngestError(msg)
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        msg = f"failed to read file_path: {file_path}"
        raise IngestError(msg) from exc


def _chunk_id(doc_id: str, version: str, index: int) -> str:
    return f"{doc_id}:{version}:{index:04d}"


def _payload(
    *,
    role_id: str,
    doc_id: str,
    doc_name: str,
    version: str,
    chunk_id: str,
    text: str,
) -> dict[str, Any]:
    return {
        "role_id": role_id,
        "doc_id": doc_id,
        "doc_name": doc_name,
        "version": version,
        "chunk_id": chunk_id,
        "text": text,
    }


def _ensure_collection(client: QdrantClient, collection: str, *, dims: int) -> None:
    if client.collection_exists(collection):
        return
    client.create_collection(
        collection_name=collection,
        vectors_config={
            DENSE_VECTOR_NAME: qmodels.VectorParams(
                size=dims,
                distance=qmodels.Distance.COSINE,
            )
        },
    )


def _stale_doc_name_filter(
    doc_name: str,
    doc_id: str,
    version: str,
) -> qmodels.Filter:
    """Points with same doc_name but not the current doc_id+version."""
    return qmodels.Filter(
        must=[
            qmodels.FieldCondition(
                key="doc_name",
                match=qmodels.MatchValue(value=doc_name),
            )
        ],
        must_not=[
            qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="doc_id",
                        match=qmodels.MatchValue(value=doc_id),
                    ),
                    qmodels.FieldCondition(
                        key="version",
                        match=qmodels.MatchValue(value=version),
                    ),
                ]
            )
        ],
    )


def _delete_stale_by_doc_name(
    client: QdrantClient,
    *,
    collection: str,
    doc_name: str,
    doc_id: str,
    version: str,
) -> None:
    client.delete(
        collection_name=collection,
        points_selector=qmodels.FilterSelector(
            filter=_stale_doc_name_filter(doc_name, doc_id, version),
        ),
    )


def ingest_document(
    *,
    role_id: str,
    doc_id: str,
    doc_name: str,
    version: str,
    content: str | None = None,
    file_path: str | None = None,
    settings: Settings | None = None,
) -> IngestResult:
    """
  Ingest one KB document: chunk → embed → upsert → delete other versions by doc_name.

  Writes the new version first, then removes stale chunks for the same ``doc_name``
  so a failed upsert does not leave only deleted data.
    """
    cfg = settings or get_settings()
    rid = role_id.strip()
    did = doc_id.strip()
    dname = doc_name.strip()
    ver = version.strip()

    if not rid or not did or not dname or not ver:
        msg = "role_id, doc_id, doc_name, and version are required"
        raise IngestError(msg)

    if content is not None and file_path is not None:
        msg = "provide only one of content or file_path"
        raise IngestError(msg)

    body = _read_content(content=content, file_path=file_path)
    if not body:
        msg = "document content is empty"
        raise IngestError(msg)

    chunks = chunk_text(
        body,
        chunk_size_tokens=effective_chunk_size_tokens(cfg),
        overlap_ratio=cfg.CHUNK_OVERLAP_RATIO,
    )
    if not chunks:
        msg = "no chunks produced from content"
        raise IngestError(msg)

    tokens_estimated = sum(estimate_tokens(c) for c in chunks)

    try:
        vectors = _embed_texts(chunks, cfg)
    except Exception as exc:
        cause = str(exc)
        if "512" in cause or "413" in cause:
            msg = (
                "embedding input exceeds provider token limit "
                f"({cfg.EMBEDDING_MAX_INPUT_TOKENS}); "
                "reduce CHUNK_SIZE_TOKENS or split the document further"
            )
        else:
            msg = f"embedding failed: {cause}"
        raise IngestError(msg) from exc

    if len(vectors) != len(chunks):
        msg = "embedding count mismatch"
        raise IngestError(msg)

    client = get_qdrant_client(cfg)
    collection = cfg.QDRANT_COLLECTION_KB

    try:
        _ensure_collection(client, collection, dims=cfg.EMBEDDING_MODEL_DIMS)
    except Exception as exc:
        msg = f"failed to ensure collection {collection}"
        raise IngestError(msg) from exc

    points: list[qmodels.PointStruct] = []
    for index, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True)):
        cid = _chunk_id(did, ver, index)
        points.append(
            qmodels.PointStruct(
                id=str(uuid.uuid4()),
                vector={DENSE_VECTOR_NAME: vector},
                payload=_payload(
                    role_id=rid,
                    doc_id=did,
                    doc_name=dname,
                    version=ver,
                    chunk_id=cid,
                    text=chunk,
                ),
            )
        )

    try:
        client.upsert(collection_name=collection, points=points, wait=True)
    except Exception as exc:
        msg = "qdrant upsert failed"
        raise IngestError(msg) from exc

    try:
        _delete_stale_by_doc_name(
            client,
            collection=collection,
            doc_name=dname,
            doc_id=did,
            version=ver,
        )
    except Exception as exc:
        msg = "qdrant delete stale chunks failed"
        raise IngestError(msg) from exc

    logger.info(
        "ingested doc_id=%s doc_name=%s version=%s chunks=%d role_id=%s",
        did,
        dname,
        ver,
        len(points),
        rid,
    )
    return IngestResult(
        doc_id=did,
        doc_name=dname,
        version=ver,
        chunks_written=len(points),
        tokens_estimated=tokens_estimated,
    )
