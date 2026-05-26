"""Pydantic models for KB document admin API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class KbChunkPreviewOut(BaseModel):
    chunk_id: str
    index: int
    text: str


class KbDocumentSummaryOut(BaseModel):
    doc_id: str
    doc_name: str
    version: str
    role_id: str
    chunks_written: int


class KbDocumentListResponse(BaseModel):
    items: list[KbDocumentSummaryOut]


class KbDocumentDetailResponse(BaseModel):
    doc_id: str
    doc_name: str
    version: str
    role_id: str
    chunks_written: int
    chunks: list[KbChunkPreviewOut] = Field(default_factory=list)
