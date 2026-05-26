"""Authentication routes: login, logout, and current user profile."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.deps import get_db_session, require_current_user
from api.errors import invalid_credentials
from auth.session_keys import SESSION_USER_ID
from db.models import User
from services.auth import authenticate_user, build_me_payload

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class RoleSummary(BaseModel):
    role_id: str
    name: str


class MeResponse(BaseModel):
    user_id: str
    username: str
    display_name: str
    is_admin: bool
    role_ids: list[str]
    roles: list[RoleSummary]


@router.post("/login", response_model=MeResponse)
def login(
    body: LoginRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db_session)],
) -> MeResponse:
    user = authenticate_user(db, body.username.strip(), body.password)
    if user is None:
        raise invalid_credentials()
    request.session[SESSION_USER_ID] = user.user_id
    payload = build_me_payload(db, user)
    return MeResponse.model_validate(payload)


@router.post("/logout", status_code=204)
def logout(request: Request) -> Response:
    request.session.clear()
    return Response(status_code=204)


me_router = APIRouter(prefix="/api", tags=["auth"])


@me_router.get("/me", response_model=MeResponse)
def me(
    user: Annotated[User, Depends(require_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> MeResponse:
    payload = build_me_payload(db, user)
    return MeResponse.model_validate(payload)
