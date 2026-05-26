"""Admin routes: roles and users CRUD (requires is_admin)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from admin import roles as role_service
from admin import users as user_service
from api.deps import get_db_session, require_admin
from api.errors import ApiError
from db.models import User

router = APIRouter(prefix="/api/admin", tags=["admin"])


class RoleOut(BaseModel):
    role_id: str
    name: str
    description: str | None
    user_count: int
    document_count: int
    created_at: datetime
    updated_at: datetime


class RoleCreateRequest(BaseModel):
    role_id: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=128)
    description: str | None = Field(default=None)


class RoleUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None


class RoleSummary(BaseModel):
    role_id: str
    name: str


class UserOut(BaseModel):
    user_id: str
    username: str
    display_name: str
    is_admin: bool
    role_ids: list[str]
    roles: list[RoleSummary]
    created_at: datetime
    updated_at: datetime


class UserCreateRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1)
    display_name: str = Field(..., min_length=1, max_length=128)
    role_ids: list[str] = Field(..., min_length=1)
    is_admin: bool = False


class UserUpdateRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=128)
    password: str | None = Field(default=None, min_length=1)
    role_ids: list[str] | None = Field(default=None, min_length=1)
    is_admin: bool | None = None


@router.get("/roles", response_model=list[RoleOut])
def list_roles(
    db: Annotated[Session, Depends(get_db_session)],
    _admin: Annotated[User, Depends(require_admin)],
) -> list[RoleOut]:
    return [RoleOut.model_validate(item) for item in role_service.list_roles(db)]


@router.get("/roles/{role_id}", response_model=RoleOut)
def get_role(
    role_id: str,
    db: Annotated[Session, Depends(get_db_session)],
    _admin: Annotated[User, Depends(require_admin)],
) -> RoleOut:
    return RoleOut.model_validate(role_service.get_role(db, role_id))


@router.post("/roles", response_model=RoleOut, status_code=201)
def create_role(
    body: RoleCreateRequest,
    db: Annotated[Session, Depends(get_db_session)],
    _admin: Annotated[User, Depends(require_admin)],
) -> RoleOut:
    try:
        role = role_service.create_role(
            db,
            role_id=body.role_id,
            name=body.name,
            description=body.description,
        )
    except ApiError:
        raise
    except ValueError as exc:
        raise ApiError(
            status_code=400,
            code="VALIDATION_ERROR",
            message=str(exc),
        ) from exc
    return RoleOut.model_validate(role)


@router.patch("/roles/{role_id}", response_model=RoleOut)
def update_role(
    role_id: str,
    body: RoleUpdateRequest,
    db: Annotated[Session, Depends(get_db_session)],
    _admin: Annotated[User, Depends(require_admin)],
) -> RoleOut:
    updates = body.model_dump(exclude_unset=True)
    role = role_service.update_role(db, role_id, updates)
    return RoleOut.model_validate(role)


@router.delete("/roles/{role_id}", status_code=204)
def delete_role(
    role_id: str,
    db: Annotated[Session, Depends(get_db_session)],
    _admin: Annotated[User, Depends(require_admin)],
) -> None:
    role_service.delete_role(db, role_id)


@router.get("/users", response_model=list[UserOut])
def list_users(
    db: Annotated[Session, Depends(get_db_session)],
    _admin: Annotated[User, Depends(require_admin)],
) -> list[UserOut]:
    return [UserOut.model_validate(item) for item in user_service.list_users(db)]


@router.get("/users/{user_id}", response_model=UserOut)
def get_user(
    user_id: str,
    db: Annotated[Session, Depends(get_db_session)],
    _admin: Annotated[User, Depends(require_admin)],
) -> UserOut:
    return UserOut.model_validate(user_service.get_user(db, user_id))


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(
    body: UserCreateRequest,
    db: Annotated[Session, Depends(get_db_session)],
    _admin: Annotated[User, Depends(require_admin)],
) -> UserOut:
    user = user_service.create_user(
        db,
        username=body.username,
        password=body.password,
        display_name=body.display_name,
        role_ids=body.role_ids,
        is_admin=body.is_admin,
    )
    return UserOut.model_validate(user)


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: str,
    body: UserUpdateRequest,
    db: Annotated[Session, Depends(get_db_session)],
    _admin: Annotated[User, Depends(require_admin)],
) -> UserOut:
    updates = body.model_dump(exclude_unset=True)
    user = user_service.update_user(db, user_id, updates)
    return UserOut.model_validate(user)


@router.delete("/users/{user_id}", status_code=204)
def delete_user(
    user_id: str,
    db: Annotated[Session, Depends(get_db_session)],
    _admin: Annotated[User, Depends(require_admin)],
) -> None:
    user_service.delete_user(db, user_id)
