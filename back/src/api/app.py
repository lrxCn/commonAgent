"""FastAPI Back stub — inject demo context and forward to Agent."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from api.auth_routes import me_router, router as auth_router
from api.call_routes import router as call_router
from admin.kb_routes import router as admin_kb_router
from admin.routes import router as admin_router
from api.deps import get_db_session, require_current_user
from api.students_routes import router as students_router
from api.errors import forbidden, register_error_handlers
from api.schemas import BackChatRequest
from db.models import User
from services.auth import load_user_roles
from services.chat_threads import ensure_thread_access, verify_thread_access
from services.context import build_agent_chat_payload
from services.forward import forward_chat_to_agent, forward_thread_history_to_agent
from settings.config import Settings, get_settings
from sqlalchemy.orm import Session


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
    application.include_router(admin_kb_router)
    application.include_router(call_router)

    @application.get("/health")
    def health(
        settings: Annotated[Settings, Depends(get_settings)],
    ) -> dict[str, str | int]:
        return {"status": "ok", "service": "common-agent-back", "port": settings.BACK_PORT}

    @application.post("/api/chat", response_model=None)
    async def api_chat(
        body: BackChatRequest,
        user: Annotated[User, Depends(require_current_user)],
        db: Annotated[Session, Depends(get_db_session)],
        settings: Annotated[Settings, Depends(get_settings)],
    ):
        ensure_thread_access(db, user_id=user.user_id, thread_id=body.thread_id)
        roles = load_user_roles(db, user.user_id)
        role_ids = [role.role_id for role in roles]
        if not role_ids:
            raise forbidden("用户未绑定角色")
        payload = build_agent_chat_payload(
            thread_id=body.thread_id,
            message=body.message,
            user_id=user.user_id,
            role_ids=role_ids,
            settings=settings,
        )
        return await forward_chat_to_agent(payload, settings=settings)

    @application.get("/api/threads/{thread_id}/messages", response_model=None)
    async def api_thread_messages(
        thread_id: str,
        user: Annotated[User, Depends(require_current_user)],
        db: Annotated[Session, Depends(get_db_session)],
        settings: Annotated[Settings, Depends(get_settings)],
        cursor: str | None = None,
        limit: int = 20,
    ):
        verify_thread_access(db, user_id=user.user_id, thread_id=thread_id)
        return await forward_thread_history_to_agent(
            thread_id,
            cursor=cursor,
            limit=limit,
            settings=settings,
        )

    return application


app = create_app()
