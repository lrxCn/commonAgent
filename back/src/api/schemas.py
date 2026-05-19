"""Public Back API request models (browser → Back)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BackChatRequest(BaseModel):
    """Body for ``POST /api/chat``; identity and tools are injected by Back."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"thread_id": "t1", "message": "hello"}],
        }
    )

    thread_id: str = Field(..., description="Conversation thread id from the client.")
    message: str = Field(..., description="User message for this turn.")

    @field_validator("thread_id")
    @classmethod
    def thread_id_non_empty(cls, value: str) -> str:
        if not value or not value.strip():
            msg = "thread_id must be a non-empty string"
            raise ValueError(msg)
        return value.strip()
