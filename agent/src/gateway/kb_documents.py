"""Gateway handlers for KB document list/get/delete."""

from __future__ import annotations

from collections.abc import Sequence

from gateway.schemas_kb import (
    KbChunkPreviewOut,
    KbDocumentDetailResponse,
    KbDocumentListResponse,
    KbDocumentSummaryOut,
)
from rag.kb_documents import KbDocumentError, delete_document, get_document, list_documents


def list_kb_documents(role_ids: Sequence[str]) -> KbDocumentListResponse:
    items = list_documents(role_ids)
    return KbDocumentListResponse(
        items=[
            KbDocumentSummaryOut(
                doc_id=item.doc_id,
                doc_name=item.doc_name,
                version=item.version,
                role_ids=item.role_ids,
                chunks_written=item.chunks_written,
            )
            for item in items
        ]
    )


def get_kb_document(doc_id: str) -> KbDocumentDetailResponse:
    detail = get_document(doc_id)
    return KbDocumentDetailResponse(
        doc_id=detail.doc_id,
        doc_name=detail.doc_name,
        version=detail.version,
        role_ids=detail.role_ids,
        chunks_written=detail.chunks_written,
        chunks=[
            KbChunkPreviewOut(
                chunk_id=chunk.chunk_id,
                index=chunk.index,
                text=chunk.text,
            )
            for chunk in detail.chunks
        ],
    )


def delete_kb_document(doc_id: str) -> None:
    delete_document(doc_id)


def map_kb_document_error(exc: KbDocumentError) -> tuple[int, str]:
    message = str(exc)
    if "not found" in message:
        return 404, message
    return 400, message
