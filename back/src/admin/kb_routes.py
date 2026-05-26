"""Admin KB document routes (requires is_admin)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from admin import kb as kb_service
from api.deps import get_db_session, require_admin
from api.errors import ApiError
from db.models import User

router = APIRouter(prefix="/api/admin/kb", tags=["admin-kb"])


class KbChunkOut(BaseModel):
    chunk_id: str
    index: int
    text: str


class KbDocumentOut(BaseModel):
    doc_id: str
    role_id: str
    doc_name: str
    version: str
    raw_content: str
    chunks_written: int
    tokens_estimated: int
    created_by: str | None
    created_at: datetime
    updated_at: datetime


class KbDocumentDetailOut(KbDocumentOut):
    chunks: list[KbChunkOut] = Field(default_factory=list)


class KbDocumentListResponse(BaseModel):
    items: list[KbDocumentOut]
    total: int
    offset: int
    limit: int


class KbDocumentCreateRequest(BaseModel):
    role_id: str = Field(..., min_length=1)
    doc_name: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1)
    doc_id: str | None = Field(default=None, max_length=128)
    version: str = Field(default="1", min_length=1, max_length=64)


class KbDocumentUpdateRequest(BaseModel):
    role_id: str = Field(..., min_length=1)
    doc_name: str | None = Field(default=None, min_length=1, max_length=255)
    raw_content: str | None = None
    version: str | None = Field(default=None, min_length=1, max_length=64)


@router.get("/documents", response_model=KbDocumentListResponse)
def list_kb_documents(
    db: Annotated[Session, Depends(get_db_session)],
    _admin: Annotated[User, Depends(require_admin)],
    role_id: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> KbDocumentListResponse:
    payload = kb_service.list_documents(
        db,
        role_id=role_id,
        keyword=keyword,
        offset=offset,
        limit=limit,
    )
    return KbDocumentListResponse.model_validate(payload)


@router.get("/documents/{doc_id}", response_model=KbDocumentDetailOut)
def get_kb_document(
    doc_id: str,
    role_id: Annotated[str, Query(min_length=1)],
    db: Annotated[Session, Depends(get_db_session)],
    _admin: Annotated[User, Depends(require_admin)],
) -> KbDocumentDetailOut:
    try:
        payload = kb_service.get_document(db, doc_id, role_id=role_id)
    except ApiError:
        raise
    return KbDocumentDetailOut.model_validate(payload)


@router.post("/documents", response_model=KbDocumentOut, status_code=201)
def create_kb_document(
    body: KbDocumentCreateRequest,
    db: Annotated[Session, Depends(get_db_session)],
    admin: Annotated[User, Depends(require_admin)],
) -> KbDocumentOut:
    try:
        payload = kb_service.create_document(
            db,
            role_id=body.role_id,
            doc_name=body.doc_name,
            content=body.content,
            created_by=admin.user_id,
            doc_id=body.doc_id,
            version=body.version,
        )
    except ApiError:
        raise
    return KbDocumentOut.model_validate(payload)


@router.patch("/documents/{doc_id}", response_model=KbDocumentOut)
def update_kb_document(
    doc_id: str,
    body: KbDocumentUpdateRequest,
    db: Annotated[Session, Depends(get_db_session)],
    _admin: Annotated[User, Depends(require_admin)],
) -> KbDocumentOut:
    try:
        payload = kb_service.update_document(
            db,
            doc_id,
            role_id=body.role_id,
            doc_name=body.doc_name,
            raw_content=body.raw_content,
            version=body.version,
        )
    except ApiError:
        raise
    return KbDocumentOut.model_validate(payload)


@router.delete("/documents/{doc_id}", status_code=204)
def delete_kb_document(
    doc_id: str,
    role_id: Annotated[str, Query(min_length=1)],
    db: Annotated[Session, Depends(get_db_session)],
    _admin: Annotated[User, Depends(require_admin)],
) -> None:
    try:
        kb_service.delete_document(db, doc_id, role_id=role_id)
    except ApiError:
        raise
