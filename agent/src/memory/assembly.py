"""Assemble system prompt and LangChain messages (K + M + rolling summary)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from memory.mem0_client import format_mem0_for_system
from memory.profile import (
    format_memory_profile_for_system,
    normalize_memory_profile,
)
from observability.tracing import attach_run_metadata
from rag.retriever import RagChunk, format_rag_chunks_for_system
from settings.config import Settings, get_settings


class ContextAssemblyError(ValueError):
    """Raised when prefix, summary coverage, and recent turns overlap."""


_TRUNCATION_SUFFIX = "...[truncated]"


@dataclass(frozen=True)
class ContextBudgetResult:
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


def _as_positive_int(value: int, *, fallback: int = 0) -> int:
    try:
        return max(0, int(value))
    except Exception:
        return fallback


def _truncate_text(text: str, max_chars: int) -> tuple[str, bool]:
    limit = _as_positive_int(max_chars)
    if limit <= 0:
        return "", bool(text)
    if len(text) <= limit:
        return text, False
    if limit <= len(_TRUNCATION_SUFFIX):
        return text[:limit], True
    return f"{text[: limit - len(_TRUNCATION_SUFFIX)]}{_TRUNCATION_SUFFIX}", True


def _message_content_text(message: BaseMessage) -> str:
    content = message.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, Mapping):
                parts.append(str(block.get("text", "")))
        return "".join(parts)
    return str(content)


def _copy_message_with_content(message: BaseMessage, content: str) -> BaseMessage:
    if isinstance(message, HumanMessage):
        return HumanMessage(
            content=content,
            additional_kwargs=dict(message.additional_kwargs),
            response_metadata=dict(message.response_metadata),
            id=message.id,
            name=message.name,
        )
    if isinstance(message, AIMessage):
        return AIMessage(
            content=content,
            additional_kwargs=dict(message.additional_kwargs),
            response_metadata=dict(message.response_metadata),
            id=message.id,
            name=message.name,
        )
    return message


def _profile_fact_count(profile_block: str) -> int:
    return sum(1 for line in profile_block.splitlines() if line.startswith("- "))


def _budget_rag_chunks(
    chunks: Sequence[RagChunk],
    settings: Settings,
) -> tuple[list[RagChunk], bool]:
    max_chunk_chars = _as_positive_int(settings.RAG_CHUNK_MAX_CHARS)
    max_context_chars = _as_positive_int(settings.RAG_CONTEXT_MAX_CHARS)
    if max_context_chars <= 0:
        return [], bool(chunks)

    out: list[RagChunk] = []
    truncated = False
    for chunk in chunks:
        text, clipped = _truncate_text(chunk.text, max_chunk_chars)
        truncated = truncated or clipped
        candidate = [*out, RagChunk(chunk.doc_id, chunk.chunk_id, text, chunk.score)]
        block = format_rag_chunks_for_system(candidate)
        if len(block) <= max_context_chars:
            out = candidate
            continue
        truncated = True
        if not out:
            ref_prefix_len = len(
                format_rag_chunks_for_system([RagChunk(chunk.doc_id, chunk.chunk_id, "", chunk.score)])
            )
            budget = max(0, max_context_chars - ref_prefix_len)
            clipped_text, _ = _truncate_text(text, budget)
            first = RagChunk(chunk.doc_id, chunk.chunk_id, clipped_text, chunk.score)
            if len(format_rag_chunks_for_system([first])) <= max_context_chars:
                out = [first]
        break
    if len(out) < len(chunks):
        truncated = True
    return out, truncated


def _budget_messages(
    messages: Sequence[BaseMessage],
    settings: Settings,
) -> tuple[list[BaseMessage], bool]:
    max_chars = _as_positive_int(settings.MODEL_MESSAGE_MAX_CHARS)
    if max_chars <= 0:
        return [], bool(messages)

    selected_reversed: list[BaseMessage] = []
    remaining = max_chars
    truncated = False
    for message in reversed(messages):
        text = _message_content_text(message)
        if len(text) <= remaining:
            selected_reversed.append(message)
            remaining -= len(text)
            continue
        if remaining > 0:
            clipped, _ = _truncate_text(text, remaining)
            selected_reversed.append(_copy_message_with_content(message, clipped))
        truncated = True
        break

    if len(selected_reversed) < len(messages):
        truncated = True
    return list(reversed(selected_reversed)), truncated


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


def build_system_prompt_with_budget(
    *,
    instructions: str,
    mem0: Sequence[str],
    summary: str | None,
    rag_chunks: Sequence[RagChunk],
    settings: Settings | None = None,
) -> tuple[str, ContextBudgetResult]:
    """Combine instructions, memory, summary, and RAG with explicit budgets."""
    cfg = settings or get_settings()
    sections: list[str] = []
    instr = instructions.strip()
    if instr:
        sections.append(instr)

    normalized = normalize_memory_profile(mem0)
    budget_truncated = False
    profile_block = format_memory_profile_for_system(
        normalized.profile,
        max_facts=cfg.MEMORY_PROFILE_MAX_FACTS,
    )
    full_profile_block = format_memory_profile_for_system(normalized.profile)
    if _profile_fact_count(profile_block) < _profile_fact_count(full_profile_block):
        budget_truncated = True
    if profile_block:
        sections.append(profile_block)

    residual_limit = _as_positive_int(cfg.MEM0_FREE_TEXT_MAX_FACTS)
    residual_facts = normalized.residual_facts[:residual_limit]
    if len(residual_facts) < len(normalized.residual_facts):
        budget_truncated = True
    mem0_block = format_mem0_for_system(residual_facts)
    if mem0_block:
        sections.append(mem0_block)

    summary_text, summary_truncated = _truncate_text(
        (summary or "").strip(),
        cfg.SUMMARY_MAX_CHARS,
    )
    budget_truncated = budget_truncated or summary_truncated
    summary_block = format_summary_for_system(summary_text)
    if summary_block:
        sections.append(summary_block)

    budgeted_chunks, rag_truncated = _budget_rag_chunks(rag_chunks, cfg)
    budget_truncated = budget_truncated or rag_truncated
    rag_block = format_rag_chunks_for_system(budgeted_chunks)
    if rag_block:
        sections.append(rag_block)

    system_str = "\n\n".join(sections)
    result = ContextBudgetResult(
        system_prompt_len=len(system_str),
        mem0_count=_profile_fact_count(profile_block) + len(residual_facts),
        memory_profile_count=_profile_fact_count(profile_block),
        mem0_free_text_count=len(residual_facts),
        rag_chunk_count=len(budgeted_chunks),
        message_count=0,
        message_chars=0,
        budget_truncated=budget_truncated,
    )
    attach_run_metadata(result.as_metadata())
    return system_str, result


def build_system_prompt(
    *,
    instructions: str,
    mem0: Sequence[str],
    summary: str | None,
    rag_chunks: Sequence[RagChunk],
) -> str:
    """Combine instructions, mem0, summary, and RAG into one system string."""
    system_str, _budget = build_system_prompt_with_budget(
        instructions=instructions,
        mem0=mem0,
        summary=summary,
        rag_chunks=rag_chunks,
    )
    return system_str


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


def build_context_with_budget(
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
) -> tuple[str, list[BaseMessage], ContextBudgetResult]:
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
    cfg = get_settings()
    k, m = _resolve_km(k, m, cfg)
    prefix_idx, _middle_idx, recent_idx = select_turn_index_ranges(len(turns), k=k, m=m)

    selected: list[int] = []
    seen: set[int] = set()
    for idx in prefix_idx + recent_idx:
        if idx not in seen:
            seen.add(idx)
            selected.append(idx)
    max_turns = _as_positive_int(cfg.MODEL_MESSAGE_MAX_TURNS)
    turn_budget_truncated = False
    if max_turns >= 0 and len(selected) > max_turns:
        selected = selected[-max_turns:] if max_turns > 0 else []
        turn_budget_truncated = True
    lc_messages = _flatten_turns(turns, selected)

    if current_text:
        kwargs: dict[str, object] = {}
        if orig_text and orig_text != current_text:
            kwargs["additional_kwargs"] = {
                _original_human_metadata_key(): orig_text,
            }
        lc_messages.append(HumanMessage(content=current_text, **kwargs))

    lc_messages, message_truncated = _budget_messages(lc_messages, cfg)

    system_str, budget = build_system_prompt_with_budget(
        instructions=instructions,
        mem0=mem0,
        summary=summary,
        rag_chunks=rag_chunks,
        settings=cfg,
    )
    message_chars = sum(len(_message_content_text(message)) for message in lc_messages)
    merged_budget = ContextBudgetResult(
        system_prompt_len=budget.system_prompt_len,
        mem0_count=budget.mem0_count,
        memory_profile_count=budget.memory_profile_count,
        mem0_free_text_count=budget.mem0_free_text_count,
        rag_chunk_count=budget.rag_chunk_count,
        message_count=len(lc_messages),
        message_chars=message_chars,
        budget_truncated=budget.budget_truncated or turn_budget_truncated or message_truncated,
    )
    attach_run_metadata(merged_budget.as_metadata())
    return system_str, lc_messages, merged_budget


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
    """Assemble system text and model messages, returning the legacy tuple."""
    system_str, lc_messages, _budget = build_context_with_budget(
        mem0=mem0,
        summary=summary,
        rag_chunks=rag_chunks,
        instructions=instructions,
        messages=messages,
        k=k,
        m=m,
        current_human=current_human,
        original_human=original_human,
    )
    return system_str, lc_messages
