"""LangGraph Store memory contracts for langmem migration (tasks 70+)."""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict, Field, field_validator

MEMORY_STORE_USERS_PREFIX: Final[tuple[str, ...]] = ("users",)
MEMORY_STORE_PROFILE_SEGMENT: Final[str] = "profile"
MEMORY_STORE_FACTS_SEGMENT: Final[str] = "facts"

MemoryStoreNamespace = tuple[str, ...]
"""LangGraph Store namespace tuple, e.g. ``("users", user_id, "profile")``."""


def profile_namespace(user_id: str) -> MemoryStoreNamespace:
    """Return the profile namespace for structured attribute upserts."""
    normalized = user_id.strip()
    if not normalized:
        raise ValueError("user_id cannot be blank")
    return (*MEMORY_STORE_USERS_PREFIX, normalized, MEMORY_STORE_PROFILE_SEGMENT)


def facts_namespace(user_id: str) -> MemoryStoreNamespace:
    """Return the collection namespace for inferred free-text facts."""
    normalized = user_id.strip()
    if not normalized:
        raise ValueError("user_id cannot be blank")
    return (*MEMORY_STORE_USERS_PREFIX, normalized, MEMORY_STORE_FACTS_SEGMENT)


class ProfileMemoryValue(BaseModel):
    """Value stored under a profile namespace key (attribute name)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    value: str
    raw_utterance: str
    source_turn_id: str
    extraction_method: str
    updated_at: str = Field(
        description="ISO 8601 timestamp when the profile field was last updated.",
    )

    @field_validator(
        "value",
        "raw_utterance",
        "source_turn_id",
        "extraction_method",
        "updated_at",
    )
    @classmethod
    def _reject_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("profile memory value text fields cannot be blank")
        return value

    def to_store_dict(self) -> dict[str, str]:
        """Serialize to the JSON value shape expected by Store ``put``."""
        return self.model_dump(mode="json")


class UserMemoryReadResult(BaseModel):
    """Normalized read result for ``fetch_user_memories`` (task 70+)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    facts: list[str] = Field(
        default_factory=list,
        description="Canonical fact strings merged from profile + collection.",
    )

    @field_validator("facts")
    @classmethod
    def _reject_blank_facts(cls, value: list[str]) -> list[str]:
        if any(not item.strip() for item in value):
            raise ValueError("fact strings cannot be blank")
        return value

    def as_fact_list(self) -> list[str]:
        """Return the legacy ``list[str]`` shape consumed by graph state today."""
        return list(self.facts)
