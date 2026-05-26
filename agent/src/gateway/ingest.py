"""Gateway handler for POST /internal/kb/ingest."""

from __future__ import annotations

from gateway.schemas_ingest import KbIngestRequest, KbIngestResponse
from rag.ingest import ingest_document


def ingest_kb(body: KbIngestRequest) -> KbIngestResponse:
    """Run KB ingest and map to API response."""
    result = ingest_document(
        role_ids=body.role_ids,
        doc_id=body.doc_id,
        doc_name=body.doc_name,
        version=body.version,
        content=body.content,
        file_path=body.file_path,
    )
    return KbIngestResponse(
        doc_id=result.doc_id,
        doc_name=result.doc_name,
        version=result.version,
        chunks_written=result.chunks_written,
        tokens_estimated=result.tokens_estimated,
    )

