"""Incremental rolling summary updates after each turn."""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from functools import lru_cache
from pathlib import Path

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from contracts.llm import ModelUseCase
from infrastructure.llm.gateway import get_llm_gateway
from memory.assembly import select_turn_index_ranges, split_into_turns
from memory.history import (
    get_rolling_summary_state,
    load_thread_messages,
    save_rolling_summary,
)
from settings.config import get_settings

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent / "prompts" / "summary_update.txt"

_summarizer_override: BaseChatModel | Callable[[str], str] | None = None


def set_summary_llm(llm: BaseChatModel | Callable[[str], str] | None) -> None:
    """Replace summarization LLM (tests). Pass None to clear."""
    global _summarizer_override
    _summarizer_override = llm


@lru_cache
def _load_prompt_template() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def format_turns_for_summary(turns: Sequence[Sequence[BaseMessage]]) -> str:
    """Serialize turn groups for the summary merge prompt."""
    if not turns:
        return "（无）"
    blocks: list[str] = []
    for index, turn in enumerate(turns, start=1):
        lines: list[str] = [f"### Turn {index}"]
        for message in turn:
            if isinstance(message, HumanMessage):
                role = "用户"
            elif isinstance(message, AIMessage):
                role = "助手"
            else:
                role = getattr(message, "type", "其他")
            content = str(message.content).strip() if message.content else ""
            if content:
                lines.append(f"{role}: {content}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def build_summary_update_prompt(existing_summary: str | None, new_turns_text: str) -> str:
    template = _load_prompt_template()
    return template.format(
        existing_summary=(existing_summary or "").strip() or "（无）",
        new_turns_text=new_turns_text.strip() or "（无）",
    )


def _invoke_summarizer(prompt: str, *, model_name: str | None = None) -> str:
    if _summarizer_override is not None:
        if hasattr(_summarizer_override, "invoke"):
            response = _summarizer_override.invoke([HumanMessage(content=prompt)])
            return str(response.content).strip()
        return str(_summarizer_override(prompt)).strip()  # type: ignore[operator]

    settings = get_settings()
    llm = get_llm_gateway(settings).chat_model(
        ModelUseCase.SUMMARY,
        model_name=model_name,
    )
    response = llm.invoke([HumanMessage(content=prompt)])
    return str(response.content).strip()


def merge_summary_increment(
    existing_summary: str | None,
    new_turns_text: str,
    *,
    model_name: str | None = None,
) -> str:
    """LLM merge of existing summary with new middle-band turns."""
    prompt = build_summary_update_prompt(existing_summary, new_turns_text)
    try:
        merged = _invoke_summarizer(prompt, model_name=model_name)
    except Exception:
        logger.exception("summary_job.merge_failed")
        if existing_summary:
            return existing_summary.strip()
        return new_turns_text.strip()

    if not merged:
        if existing_summary:
            return existing_summary.strip()
        return new_turns_text.strip()
    return merged


def select_new_middle_turns(
    all_messages: Sequence[BaseMessage],
    *,
    k: int | None,
    m: int | None,
    summarized_through: int,
) -> tuple[list[list[BaseMessage]], int]:
    """Return unsummarized middle-band turns and the new exclusive through index."""
    turns = split_into_turns(all_messages)
    n = len(turns)
    if n == 0:
        return [], summarized_through

    resolved_k, resolved_m = k, m
    if resolved_k is None or resolved_m is None:
        settings = get_settings()
        if resolved_k is None:
            resolved_k = settings.CONTEXT_PREFIX_TURNS
        if resolved_m is None:
            resolved_m = settings.CONTEXT_RECENT_TURNS

    _, middle_indices, _ = select_turn_index_ranges(
        n,
        k=resolved_k,
        m=resolved_m,
    )
    if not middle_indices:
        return [], summarized_through

    summary_end = max(resolved_k, n - resolved_m)
    start = max(resolved_k, summarized_through)
    if start >= summary_end:
        return [], summarized_through

    new_indices = [idx for idx in middle_indices if start <= idx < summary_end]
    if not new_indices:
        return [], summarized_through

    new_turns = [turns[idx] for idx in new_indices]
    return new_turns, summary_end


def update_rolling_summary(
    thread_id: str,
    new_messages: Sequence[BaseMessage],
    k: int | None = None,
    m: int | None = None,
    *,
    model_name: str | None = None,
) -> str | None:
    """Incrementally update rolling summary for ``thread_id`` (middle band only).

    ``new_messages`` is accepted for API compatibility; the job reads the full
    thread from the checkpointer to determine which middle turns are new since
    the last summary checkpoint.
    """
    del new_messages  # full thread is authoritative for turn indexing

    all_messages = load_thread_messages(thread_id)
    if not all_messages:
        return None

    existing_summary, through_raw = get_rolling_summary_state(thread_id)
    settings = get_settings()
    resolved_k = k if k is not None else settings.CONTEXT_PREFIX_TURNS
    summarized_through = through_raw if through_raw is not None else resolved_k

    new_turns, new_through = select_new_middle_turns(
        all_messages,
        k=k,
        m=m,
        summarized_through=summarized_through,
    )
    if not new_turns:
        return existing_summary

    new_turns_text = format_turns_for_summary(new_turns)
    merged = merge_summary_increment(
        existing_summary,
        new_turns_text,
        model_name=model_name,
    )
    save_rolling_summary(thread_id, merged, through_turn=new_through)
    return merged
