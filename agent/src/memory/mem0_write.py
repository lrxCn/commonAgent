"""Extractive mem0 writes after each turn (local OSS Memory + Qdrant only)."""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from functools import lru_cache
from pathlib import Path
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from memory.mem0_client import Mem0UserIdError, get_local_memory, _require_user_id
from settings.config import Settings, get_settings

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent / "prompts" / "mem0_extract.txt"

_extractor_override: BaseChatModel | Callable[[str], str] | None = None
_memory_add_override: Callable[..., Any] | None = None


def set_mem0_extract_llm(llm: BaseChatModel | Callable[[str], str] | None) -> None:
    """Replace fact-extraction LLM (tests). Pass None to clear."""
    global _extractor_override
    _extractor_override = llm


def set_mem0_add_fn(fn: Callable[..., Any] | None) -> None:
    """Replace mem0 ``Memory.add`` call (tests). Pass None to clear."""
    global _memory_add_override
    _memory_add_override = fn


def reset_mem0_write_overrides() -> None:
    set_mem0_extract_llm(None)
    set_mem0_add_fn(None)


@lru_cache
def _load_prompt_template() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def format_turn_transcript(turn_messages: Sequence[BaseMessage]) -> str:
    """Compact single-turn transcript for extraction (not full thread history)."""
    lines: list[str] = []
    for message in turn_messages:
        if isinstance(message, HumanMessage):
            role = "用户"
        elif isinstance(message, AIMessage):
            role = "助手"
        else:
            role = getattr(message, "type", "其他")
        content = str(message.content).strip() if message.content else ""
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines)


def build_mem0_extraction_prompt(turn_text: str) -> str:
    return _load_prompt_template().format(turn_text=turn_text.strip() or "（无）")


def _create_chat_model(settings: Settings, model_name: str | None) -> BaseChatModel:
    from langchain_openai import ChatOpenAI

    name = (model_name or settings.OPENAI_MODEL_NAME).strip()
    return ChatOpenAI(
        model=name,
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL,
        temperature=0,
    )


def _invoke_extractor(prompt: str, *, model_name: str | None = None) -> str:
    if _extractor_override is not None:
        if hasattr(_extractor_override, "invoke"):
            response = _extractor_override.invoke([HumanMessage(content=prompt)])
            return str(response.content).strip()
        return str(_extractor_override(prompt)).strip()  # type: ignore[operator]

    settings = get_settings()
    llm = _create_chat_model(settings, model_name)
    response = llm.invoke([HumanMessage(content=prompt)])
    return str(response.content).strip()


def extract_facts_from_turn(
    turn_messages: Sequence[BaseMessage],
    *,
    model_name: str | None = None,
) -> list[str]:
    """Run extraction prompt on a single turn; returns fact strings (may be empty)."""
    turn_text = format_turn_transcript(turn_messages)
    if not turn_text.strip():
        return []

    prompt = build_mem0_extraction_prompt(turn_text)
    try:
        raw = _invoke_extractor(prompt, model_name=model_name)
    except Exception:
        logger.exception("mem0_write.extract_failed")
        return []

    if not raw or raw.strip().upper() == "NONE":
        return []

    facts: list[str] = []
    for line in raw.splitlines():
        text = line.strip()
        if text.startswith("- "):
            text = text[2:].strip()
        elif text.startswith("* "):
            text = text[2:].strip()
        if text and text.upper() != "NONE":
            facts.append(text)
    return facts


def build_mem0_add_payload(facts: list[str]) -> list[dict[str, str]]:
    """Short messages for mem0.add — extracted facts only, not full transcript."""
    body = "\n".join(f"- {fact}" for fact in facts)
    return [{"role": "user", "content": f"User preference facts:\n{body}"}]


def extract_and_store(
    user_id: str,
    turn_messages: Sequence[BaseMessage],
    *,
    model_name: str | None = None,
) -> list[str]:
    """Extract preference facts from one turn and store via local mem0 Memory.add."""
    uid = _require_user_id(user_id)
    settings = get_settings()
    if settings.MEM0_MOCK:
        return []

    facts = extract_facts_from_turn(turn_messages, model_name=model_name)
    if not facts:
        return []

    payload = build_mem0_add_payload(facts)
    try:
        if _memory_add_override is not None:
            _memory_add_override(payload, user_id=uid, infer=False)
        else:
            memory = get_local_memory()
            memory.add(payload, user_id=uid, infer=False)
    except Mem0UserIdError:
        raise
    except Exception:
        logger.exception("mem0_write.store_failed", extra={"user_id": uid})
        return facts

    return facts
