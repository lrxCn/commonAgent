"""Pydantic models for KB ingest API (see root README API contract)."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, Field, model_validator


class KbIngestRequest(BaseModel):
    """Internal KB ingest body."""

    role_id: str = Field(..., min_length=1, description="Role for Qdrant payload filtering.")
    doc_id: str = Field(..., min_length=1, description="Stable document identifier.")
    doc_name: str = Field(..., min_length=1, description="Logical name; stale chunks removed by this key.")
    version: str = Field(..., min_length=1, description="Document version string.")
    content: str | None = Field(
        default=None,
        description="Inline document text.",
    )
    file_path: str | None = Field(
        default=None,
        description="Internal filesystem path to UTF-8 text (mutually exclusive with content).",
    )

    @model_validator(mode="after")
    def _content_or_file_path(self) -> Self:
        has_content = self.content is not None and self.content.strip() != ""
        has_file = self.file_path is not None and str(self.file_path).strip() != ""
        if has_content and has_file:
            msg = "provide only one of content or file_path"
            raise ValueError(msg)
        if not has_content and not has_file:
            msg = "content or file_path is required"
            raise ValueError(msg)
        return self


class KbIngestResponse(BaseModel):
    """KB ingest success payload."""

    doc_id: str
    doc_name: str
    version: str
    chunks_written: int
    tokens_estimated: int
