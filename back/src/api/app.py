"""FastAPI Back stub — inject demo context and forward to Agent."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.schemas import BackChatRequest
from services.context import build_agent_chat_payload
from services.forward import forward_chat_to_agent
from settings.config import Settings, get_settings


def create_app() -> FastAPI:
    application = FastAPI(
        title="commonAgent Back",
        description=(
            "Public gateway stub: simulates post-login context injection and "
            "forwards to the internal Agent. Real auth belongs here; Agent is intranet-only."
        ),
        version="0.1.0",
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:3000",
            "http://localhost:3000",
        ],
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

    @application.get("/health")
    def health(
        settings: Annotated[Settings, Depends(get_settings)],
    ) -> dict[str, str | int]:
        return {"status": "ok", "service": "common-agent-back", "port": settings.BACK_PORT}

    @application.post("/api/chat", response_model=None)
    async def api_chat(
        body: BackChatRequest,
        settings: Annotated[Settings, Depends(get_settings)],
    ):
        payload = build_agent_chat_payload(
            thread_id=body.thread_id,
            message=body.message,
            settings=settings,
        )
        return await forward_chat_to_agent(payload, settings=settings)

    return application


app = create_app()
