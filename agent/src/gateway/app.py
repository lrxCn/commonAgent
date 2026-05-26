"""FastAPI gateway — health and internal chat (graph + SSE / JSON)."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse

from gateway.chat import (
    build_chat_response,
    invoke_chat_turn,
    iter_chat_sse_events,
    iter_sse_text_events,
)
from gateway.history import list_thread_messages
from gateway.ingest import ingest_kb
from gateway.kb_documents import (
    delete_kb_document,
    get_kb_document,
    list_kb_documents,
    map_kb_document_error,
)
from gateway.schemas import ChatRequest, ChatResponse
from gateway.schemas_history import HistoryMessagesResponse
from gateway.schemas_ingest import KbIngestRequest, KbIngestResponse
from gateway.schemas_kb import KbDocumentDetailResponse, KbDocumentListResponse
from rag.ingest import IngestError
from rag.kb_documents import KbDocumentError
from guardrails.inbound import check_inbound
from memory.history import ThreadIdError
from observability.tracing import configure_tracing_from_settings
from settings.config import Settings, get_settings


def create_app() -> FastAPI:
    """Build the gateway application (factory for tests)."""
    configure_tracing_from_settings()
    application = FastAPI(
        title="commonAgent Gateway",
        description="Internal HTTP gateway for Back → Agent chat and APIs.",
        version="0.1.0",
    )

    @application.get("/health")
    def health(
        settings: Annotated[Settings, Depends(get_settings)],
    ) -> dict[str, str | int]:
        return {"status": "ok", "service": "agent-gateway", "port": settings.AGENT_PORT}

    @application.post("/internal/chat", response_model=None)
    def internal_chat(
        body: ChatRequest,
        settings: Annotated[Settings, Depends(get_settings)],
    ) -> ChatResponse | StreamingResponse:
        guard = check_inbound(body.message, settings=settings)
        if not guard.allowed:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": guard.reason_code or "policy_violation",
                    "message": guard.message,
                },
            )

        if not body.context.tools:
            return StreamingResponse(
                iter_chat_sse_events(body),
                media_type="text/event-stream",
            )

        outcome = invoke_chat_turn(body)
        if outcome.kind == "client_actions":
            return build_chat_response(outcome)

        return StreamingResponse(
            iter_sse_text_events(outcome.text or ""),
            media_type="text/event-stream",
        )

    @application.post(
        "/internal/kb/ingest",
        response_model=KbIngestResponse,
        tags=["kb"],
    )
    def internal_kb_ingest(body: KbIngestRequest) -> KbIngestResponse:
        try:
            return ingest_kb(body)
        except IngestError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @application.get(
        "/internal/kb/documents",
        response_model=KbDocumentListResponse,
        tags=["kb"],
    )
    def internal_kb_list_documents(
        role_id: Annotated[list[str], Query(min_length=1)],
    ) -> KbDocumentListResponse:
        ids = [item.strip() for item in role_id if item and item.strip()]
        if not ids:
            raise HTTPException(status_code=400, detail="role_id query parameter is required")
        try:
            return list_kb_documents(ids)
        except KbDocumentError as exc:
            status, detail = map_kb_document_error(exc)
            raise HTTPException(status_code=status, detail=detail) from exc

    @application.get(
        "/internal/kb/documents/{doc_id}",
        response_model=KbDocumentDetailResponse,
        tags=["kb"],
    )
    def internal_kb_get_document(
        doc_id: str,
        role_id: str,
    ) -> KbDocumentDetailResponse:
        if not role_id.strip():
            raise HTTPException(status_code=400, detail="role_id query parameter is required")
        try:
            return get_kb_document(doc_id, role_id)
        except KbDocumentError as exc:
            status, detail = map_kb_document_error(exc)
            raise HTTPException(status_code=status, detail=detail) from exc

    @application.delete(
        "/internal/kb/documents/{doc_id}",
        status_code=204,
        tags=["kb"],
    )
    def internal_kb_delete_document(doc_id: str, role_id: str) -> None:
        if not role_id.strip():
            raise HTTPException(status_code=400, detail="role_id query parameter is required")
        try:
            delete_kb_document(doc_id, role_id)
        except KbDocumentError as exc:
            status, detail = map_kb_document_error(exc)
            raise HTTPException(status_code=status, detail=detail) from exc

    @application.get(
        "/internal/threads/{thread_id}/messages",
        response_model=HistoryMessagesResponse,
        tags=["history"],
    )
    def internal_thread_messages(
        thread_id: str,
        cursor: str | None = None,
        limit: int = 20,
    ) -> HistoryMessagesResponse:
        try:
            return list_thread_messages(thread_id, cursor=cursor, limit=limit)
        except ThreadIdError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return application


app = create_app()
