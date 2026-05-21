"""Assemble system prompt and LangChain messages (K + M + rolling summary)."""

from __future__ import annotations

from collections.abc import Sequence

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from memory.mem0_client import format_mem0_for_system
from memory.profile import (
    format_memory_profile_for_system,
    normalize_memory_profile,
)
from rag.retriever import RagChunk, format_rag_chunks_for_system
from settings.config import Settings, get_settings


class ContextAssemblyError(ValueError):
    """Raised when prefix, summary coverage, and recent turns overlap."""


def _resolve_km(
    k: int | None,
    m: int | None,
    settings: Settings | None = None,
) -> tuple[int, int]:
    cfg = settings or get_settings()
    return (
        cfg.CONTEXT_PREFIX_TURNS if k is None else k,
        cfg.CONTEXT_RECENT_TURNS if m is None else m,
    )


def _original_human_metadata_key(settings: Settings | None = None) -> str:
    return (settings or get_settings()).CONTEXT_ORIGINAL_HUMAN_METADATA_KEY


def split_into_turns(messages: Sequence[BaseMessage]) -> list[list[BaseMessage]]:
    """Group messages into turns; each turn starts with a human message."""
    turns: list[list[BaseMessage]] = []
    current: list[BaseMessage] = []
    for message in messages:
        if isinstance(message, HumanMessage) and current:
            turns.append(current)
            current = [message]
        else:
            current.append(message)
    if current:
        turns.append(current)
    return turns


def select_turn_index_ranges(
    turn_count: int,
    *,
    k: int | None = None,
    m: int | None = None,
) -> tuple[list[int], list[int], list[int]]:
    """Return prefix, summary-covered, and recent turn indices (0-based).

  Summary covers turns ``[K+1, N-M]`` (1-based), i.e. indices ``[k, n-m)`` when ``n-m > k``.
  Prefix and recent are merged in order without duplicate indices.
    """
    if turn_count < 0:
        raise ValueError("turn_count must be non-negative")
    k, m = _resolve_km(k, m)
    if k < 0 or m < 0:
        raise ValueError("k and m must be non-negative")

    n = turn_count
    if n == 0:
        return [], [], []

    prefix_end = min(k, n)
    recent_start = max(0, n - m)
    summary_end = max(k, n - m)

    prefix = list(range(0, prefix_end))
    middle = list(range(k, summary_end)) if k < summary_end else []
    recent = list(range(recent_start, n))

    merged: list[int] = []
    seen: set[int] = set()
    for idx in prefix + recent:
        if idx not in seen:
            seen.add(idx)
            merged.append(idx)

    if middle:
        overlap = seen.intersection(middle)
        if overlap:
            raise ContextAssemblyError(
                f"summary interval overlaps prefix/recent at turn indices: {sorted(overlap)}"
            )

    return prefix, middle, recent


def format_summary_for_system(summary: str | None) -> str:
    """Format rolling summary for the system prompt."""
    text = (summary or "").strip()
    if not text:
        return ""
    return "\n".join(["## Conversation summary", "", text])


def build_system_prompt(
    *,
    instructions: str,
    mem0: Sequence[str],
    summary: str | None,
    rag_chunks: Sequence[RagChunk],
) -> str:
    """Combine instructions, mem0, summary, and RAG into one system string."""
    sections: list[str] = []
    instr = instructions.strip()
    if instr:
        sections.append(instr)

    normalized = normalize_memory_profile(mem0)
    profile_block = format_memory_profile_for_system(normalized.profile)
    if profile_block:
        sections.append(profile_block)

    mem0_block = format_mem0_for_system(normalized.residual_facts)
    if mem0_block:
        sections.append(mem0_block)

    summary_block = format_summary_for_system(summary)
    if summary_block:
        sections.append(summary_block)

    rag_block = format_rag_chunks_for_system(rag_chunks)
    if rag_block:
        sections.append(rag_block)

    return "\n\n".join(sections)


def _flatten_turns(turns: list[list[BaseMessage]], indices: Sequence[int]) -> list[BaseMessage]:
    out: list[BaseMessage] = []
    for idx in indices:
        out.extend(turns[idx])
    return out


def _split_history_and_current(
    messages: Sequence[BaseMessage],
    *,
    current_human: str | None = None,
    original_human: str | None = None,
) -> tuple[list[BaseMessage], str | None, str | None]:
    history = list(messages)
    if current_human is not None:
        return history, current_human, original_human

    if history and isinstance(history[-1], HumanMessage):
        last = history[-1]
        text = str(last.content).strip()
        orig = original_human
        if orig is None:
            raw = last.additional_kwargs.get(_original_human_metadata_key())
            if raw is not None:
                orig = str(raw).strip() or None
        return history[:-1], text or None, orig

    return history, None, None


def build_context(
    mem0: list[str],
    summary: str | None,
    rag_chunks: Sequence[RagChunk],
    instructions: str,
    messages: Sequence[BaseMessage],
    k: int | None = None,
    m: int | None = None,
    *,
    current_human: str | None = None,
    original_human: str | None = None,
) -> tuple[str, list[BaseMessage]]:
    """Assemble system text and model messages (prefix K + recent M + current human).

    Historical turns between prefix and recent are represented only via ``summary``
    (coverage ``[K+1, N-M]``). Raises :class:`ContextAssemblyError` if slices overlap.
    """
    history, current_text, orig_text = _split_history_and_current(
        messages,
        current_human=current_human,
        original_human=original_human,
    )
    turns = split_into_turns(history)
    k, m = _resolve_km(k, m)
    prefix_idx, _middle_idx, recent_idx = select_turn_index_ranges(len(turns), k=k, m=m)

    selected: list[int] = []
    seen: set[int] = set()
    for idx in prefix_idx + recent_idx:
        if idx not in seen:
            seen.add(idx)
            selected.append(idx)
    lc_messages = _flatten_turns(turns, selected)

    if current_text:
        kwargs: dict[str, object] = {}
        if orig_text and orig_text != current_text:
            kwargs["additional_kwargs"] = {
                _original_human_metadata_key(): orig_text,
            }
        lc_messages.append(HumanMessage(content=current_text, **kwargs))

    system_str = build_system_prompt(
        instructions=instructions,
        mem0=mem0,
        summary=summary,
        rag_chunks=rag_chunks,
    )
    return system_str, lc_messages
