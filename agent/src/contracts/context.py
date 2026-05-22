"""Context assembly contracts shared by memory and graph layers."""

from __future__ import annotations

from dataclasses import dataclass

from langchain_core.messages import BaseMessage

from contracts.rag import RagChunk


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


@dataclass(frozen=True)
class ContextSources:
    """Inputs used to produce a model context bundle."""

    mem0: tuple[str, ...]
    summary: str | None
    rag_chunks: tuple[RagChunk, ...]
    current_human: str | None
    original_human: str | None

    def as_metadata(self) -> dict[str, object]:
        return {
            "source_mem0_count": len(self.mem0),
            "source_summary_len": len(self.summary or ""),
            "source_rag_chunk_count": len(self.rag_chunks),
            "source_current_human_len": len(self.current_human or ""),
            "source_original_human_len": len(self.original_human or ""),
        }


@dataclass(frozen=True)
class ContextBundle:
    """Single source of truth for model context in one graph turn."""

    system_prompt: str
    model_messages: tuple[BaseMessage, ...]
    budget: ContextBudget
    sources: ContextSources

    @property
    def messages(self) -> list[BaseMessage]:
        """Return model messages as a mutable list for LangChain invocations."""
        return list(self.model_messages)

    def budget_metadata(self) -> dict[str, object]:
        return self.budget.as_metadata()
