"""FastAPI Back stub — inject demo context and forward to Agent."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from api.auth_routes import me_router, router as auth_router
from admin.routes import router as admin_router
from api.students_routes import router as students_router
from api.errors import register_error_handlers
from api.schemas import BackChatRequest
from services.context import build_agent_chat_payload
from services.forward import forward_chat_to_agent
from settings.config import Settings, get_settings


def create_app() -> FastAPI:
    settings = get_settings()

    application = FastAPI(
        title="commonAgent Back",
        description=(
            "Public gateway: Cookie Session auth, business APIs, and "
            "forwarding to the internal Agent."
        ),
        version="0.1.0",
    )

    register_error_handlers(application)

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list(),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type"],
    )
    application.add_middleware(
        SessionMiddleware,
        secret_key=settings.SESSION_SECRET,
        same_site="lax",
        https_only=False,
    )

    application.include_router(auth_router)
    application.include_router(me_router)
    application.include_router(students_router)
    application.include_router(admin_router)

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
