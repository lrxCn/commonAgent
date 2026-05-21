"""Context assembly contracts shared by memory and graph layers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ContextBudget:
    """Budget metadata for one model context assembly."""

    system_prompt_len: int
    mem0_count: int
    memory_profile_count: int
    mem0_free_text_count: int
    rag_chunk_count: int
    message_count: int
    message_chars: int
    budget_truncated: bool

    def as_metadata(self) -> dict[str, object]:
        return {
            "system_prompt_len": self.system_prompt_len,
            "mem0_count": self.mem0_count,
            "memory_profile_count": self.memory_profile_count,
            "mem0_free_text_count": self.mem0_free_text_count,
            "rag_chunk_count": self.rag_chunk_count,
            "message_count": self.message_count,
            "message_chars": self.message_chars,
            "budget_truncated": self.budget_truncated,
        }
