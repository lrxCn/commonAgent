"""FastAPI gateway — health and internal chat (graph + SSE / JSON)."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import StreamingResponse

from gateway.chat import build_chat_response, invoke_chat_turn, iter_sse_text_events
from gateway.history import list_thread_messages
from gateway.ingest import ingest_kb
from gateway.schemas import ChatRequest, ChatResponse
from gateway.schemas_history import HistoryMessagesResponse
from gateway.schemas_ingest import KbIngestRequest, KbIngestResponse
from rag.ingest import IngestError
from guardrails.inbound import check_inbound
from memory.history import ThreadIdError
from settings.config import Settings, get_settings


def create_app() -> FastAPI:
    """Build the gateway application (factory for tests)."""
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
