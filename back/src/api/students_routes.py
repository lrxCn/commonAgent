"""Student CRUD routes — all authenticated users share the full table."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.deps import get_db_session, require_current_user
from api.errors import ApiError
from db.models import User
from services import students as student_service

router = APIRouter(prefix="/api/students", tags=["students"])


class StudentOut(BaseModel):
    student_id: str
    student_no: str
    name: str
    class_name: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class StudentListResponse(BaseModel):
    items: list[StudentOut]
    total: int
    offset: int
    limit: int


class StudentCreateRequest(BaseModel):
    student_no: str = Field(..., min_length=1, max_length=32)
    name: str = Field(..., min_length=1, max_length=128)
    class_name: str | None = Field(default=None, max_length=64)
    status: str | None = Field(default="active", max_length=32)


class StudentUpdateRequest(BaseModel):
    student_no: str | None = Field(default=None, min_length=1, max_length=32)
    name: str | None = Field(default=None, min_length=1, max_length=128)
    class_name: str | None = Field(default=None, max_length=64)
    status: str | None = Field(default=None, max_length=32)


class BatchDeleteRequest(BaseModel):
    student_ids: list[str] = Field(..., min_length=1)


class BatchDeleteResponse(BaseModel):
    deleted: int


@router.get("", response_model=StudentListResponse)
def list_students(
    db: Annotated[Session, Depends(get_db_session)],
    _user: Annotated[User, Depends(require_current_user)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    search: Annotated[str | None, Query(max_length=128)] = None,
    status: Annotated[str | None, Query(max_length=32)] = None,
    class_name: Annotated[str | None, Query(max_length=64)] = None,
) -> StudentListResponse:
    rows, total = student_service.list_students(
        db,
        offset=offset,
        limit=limit,
        search=search,
        status=status,
        class_name=class_name,
    )
    return StudentListResponse(
        items=[StudentOut.model_validate(student_service.student_to_dict(row)) for row in rows],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/meta/class-names", response_model=list[str])
def list_class_names(
    db: Annotated[Session, Depends(get_db_session)],
    _user: Annotated[User, Depends(require_current_user)],
) -> list[str]:
    return student_service.list_distinct_class_names(db)


@router.get("/{student_id}", response_model=StudentOut)
def get_student(
    student_id: str,
    db: Annotated[Session, Depends(get_db_session)],
    _user: Annotated[User, Depends(require_current_user)],
) -> StudentOut:
    student = student_service.get_student(db, student_id)
    return StudentOut.model_validate(student_service.student_to_dict(student))


@router.post("", response_model=StudentOut, status_code=201)
def create_student(
    body: StudentCreateRequest,
    db: Annotated[Session, Depends(get_db_session)],
    user: Annotated[User, Depends(require_current_user)],
) -> StudentOut:
    try:
        student = student_service.create_student(
            db,
            student_no=body.student_no,
            name=body.name,
            class_name=body.class_name,
            status=body.status,
            created_by=user.user_id,
        )
    except ValueError as exc:
        raise ApiError(
            status_code=400,
            code="VALIDATION_ERROR",
            message=str(exc),
        ) from exc
    return StudentOut.model_validate(student_service.student_to_dict(student))


@router.patch("/{student_id}", response_model=StudentOut)
def update_student(
    student_id: str,
    body: StudentUpdateRequest,
    db: Annotated[Session, Depends(get_db_session)],
    _user: Annotated[User, Depends(require_current_user)],
) -> StudentOut:
    updates = body.model_dump(exclude_unset=True)
    try:
        student = student_service.update_student(db, student_id, updates)
    except ValueError as exc:
        raise ApiError(
            status_code=400,
            code="VALIDATION_ERROR",
            message=str(exc),
        ) from exc
    return StudentOut.model_validate(student_service.student_to_dict(student))


@router.delete("/{student_id}", status_code=204)
def delete_student(
    student_id: str,
    db: Annotated[Session, Depends(get_db_session)],
    _user: Annotated[User, Depends(require_current_user)],
) -> None:
    student_service.delete_student(db, student_id)


@router.post("/batch-delete", response_model=BatchDeleteResponse)
def batch_delete_students(
    body: BatchDeleteRequest,
    db: Annotated[Session, Depends(get_db_session)],
    _user: Annotated[User, Depends(require_current_user)],
) -> BatchDeleteResponse:
    deleted = student_service.batch_delete_students(db, body.student_ids)
    return BatchDeleteResponse(deleted=deleted)
