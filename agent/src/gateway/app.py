"""FastAPI gateway — health and internal chat (stub until graph wiring)."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException

from gateway.schemas import ChatRequest
from guardrails.inbound import check_inbound
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

    @application.post("/internal/chat")
    def internal_chat(
        body: ChatRequest,
        settings: Annotated[Settings, Depends(get_settings)],
    ) -> dict[str, str]:
        guard = check_inbound(body.message, settings=settings)
        if not guard.allowed:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": guard.reason_code or "policy_violation",
                    "message": guard.message,
                },
            )
        return {"status": "stub", "thread_id": body.thread_id}

    return application


app = create_app()
