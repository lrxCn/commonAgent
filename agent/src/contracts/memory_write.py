"""Structured memory write contracts for control-plane → storage-plane handoff."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MemorySubject(str, Enum):
    """Who the structured memory fact belongs to."""

    USER = "user"
    ORG = "org"


class MemoryWriteMode(str, Enum):
    """How a post-turn memory write is performed."""

    STRUCTURED = "structured"
    INFERRED = "inferred"


class ExtractionMethod(str, Enum):
    """How the memory payload was produced."""

    SLOT_FILL_V1 = "slot_fill_v1"
    MEM0_INFER = "mem0_infer"


class StructuredMemoryRecord(BaseModel):
    """Deterministic memory write payload emitted by the control plane (fast path)."""

    model_config = ConfigDict(extra="forbid", use_enum_values=True, frozen=True)

    subject: MemorySubject
    attribute: str
    value: str
    raw_utterance: str
    confidence: float = Field(ge=0.0, le=1.0)
    source_turn_id: str
    extraction_method: str = ExtractionMethod.SLOT_FILL_V1.value

    @field_validator(
        "attribute",
        "value",
        "raw_utterance",
        "source_turn_id",
        "extraction_method",
    )
    @classmethod
    def _reject_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("structured memory record text fields cannot be blank")
        return value

    def to_trace_dict(self) -> dict[str, object]:
        """Serialize to a stable dict shape for traces, evals, and metadata."""
        return self.model_dump(mode="json")


class MemoryWriteExpectation(BaseModel):
    """Target-state write expectation used by eval seeds and future runners."""

    model_config = ConfigDict(extra="forbid", use_enum_values=True, frozen=True)

    mode: MemoryWriteMode
    infer: bool
    expected_record: StructuredMemoryRecord | None = None
    expected_final_status: str | None = None
    forbidden_final_status: tuple[str, ...] = ()

    @field_validator("expected_final_status")
    @classmethod
    def _reject_blank_status(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("expected_final_status cannot be blank")
        return value

    @field_validator("forbidden_final_status")
    @classmethod
    def _reject_blank_forbidden(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not item.strip() for item in value):
            raise ValueError("forbidden_final_status items cannot be blank")
        return value
