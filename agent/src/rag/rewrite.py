"""Query rewrite using mem0 + short-term context (no RAG)."""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from functools import lru_cache
from pathlib import Path
from typing import TypedDict

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from memory.mem0_client import format_mem0_for_system
from observability.tracing import rewrite_traceable
from rag.intent import has_knowledge_intent, is_chitchat
from settings.config import Settings, get_settings

_PROMPT_PATH = Path(__file__).parent / "prompts" / "rewrite.txt"

_llm_override: BaseChatModel | Callable[[str], str] | None = None

_ANAPHORA_RE = re.compile(
    r"(?:它|这个|那个|上述|刚才|继续|还有吗|后者|前者|这般|那样|如此|同上|前述)",
    re.IGNORECASE,
)


class RewriteNodeState(TypedDict, total=False):
    """Minimal state slice for rewrite_node (full AgentState comes in task 13)."""

    user_message: str
    mem0_memories: list[str]
    recent_messages: list[BaseMessage]
    messages: list[BaseMessage]
    rewritten_query: str


def set_rewrite_llm(llm: BaseChatModel | Callable[[str], str] | None) -> None:
    """Replace the LLM used by rewrite_query (tests). Pass None to clear."""
    global _llm_override
    _llm_override = llm


@lru_cache
def _load_prompt_template() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def format_recent_messages(messages: Sequence[BaseMessage]) -> str:
    """Serialize recent messages for the rewrite prompt."""
    if not messages:
        return "（无）"
    lines: list[str] = []
    for message in messages:
        if isinstance(message, HumanMessage):
            role = "用户"
        elif isinstance(message, AIMessage):
            role = "助手"
        else:
            role = message.type.capitalize() if getattr(message, "type", None) else "其他"
        content = str(message.content).strip() if message.content else ""
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines) if lines else "（无）"


def build_rewrite_prompt(
    user_message: str,
    mem0_text: str,
    recent_messages: Sequence[BaseMessage],
) -> str:
    """Fill the rewrite prompt template (mem0 + short-term only; no RAG)."""
    template = _load_prompt_template()
    mem0_block = mem0_text.strip() if mem0_text.strip() else "（无）"
    return template.format(
        user_message=user_message.strip(),
        mem0_text=mem0_block,
        recent_messages_text=format_recent_messages(recent_messages),
    )


def _has_anaphora(message: str) -> bool:
    return _ANAPHORA_RE.search(message.strip()) is not None


def should_rewrite(
    user_message: str,
    *,
    recent_messages: Sequence[BaseMessage],
    mem0_memories: Sequence[str] | None = None,
) -> tuple[bool, str]:
    """
    Return ``(need_llm_rewrite, reason_code)``.

    ``reason_code`` is for tracing only; when ``need_llm_rewrite`` is False the
    caller must not invoke the rewrite LLM.
    """
    text = user_message.strip()
    if not text:
        return False, "empty"

    if is_chitchat(text):
        return False, "chitchat"

    settings = get_settings()
    min_len = settings.REWRITE_MIN_SELF_CONTAINED_LEN
    memories = list(mem0_memories or [])
    recent = list(recent_messages or [])
    has_mem0 = bool(memories)
    has_recent = bool(recent)

    if not has_recent and not has_mem0:
        if not _has_anaphora(text) and len(text) >= min_len:
            return False, "standalone_no_context"

    if (
        not _has_anaphora(text)
        and len(text) >= min_len
        and has_knowledge_intent(text)
    ):
        return False, "self_contained"

    return True, "needs_disambiguation"


def _create_chat_model(settings: Settings, model_name: str | None) -> BaseChatModel:
    from langchain_openai import ChatOpenAI

    name = (model_name or settings.REWRITE_MODEL_NAME or settings.OPENAI_MODEL_NAME).strip()
    return ChatOpenAI(
        model=name,
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL,
        temperature=0,
    )


def _invoke_llm(prompt: str, *, model_name: str | None = None) -> str:
    if _llm_override is not None:
        if hasattr(_llm_override, "invoke"):
            response = _llm_override.invoke([HumanMessage(content=prompt)])
            return str(response.content).strip()
        return str(_llm_override(prompt)).strip()  # type: ignore[operator]

    settings = get_settings()
    llm = _create_chat_model(settings, model_name)
    response = llm.invoke([HumanMessage(content=prompt)])
    return str(response.content).strip()


@rewrite_traceable()
def rewrite_passthrough(
    user_message: str,
    *,
    rewrite_skip_reason: str,
    rewrite_skipped: bool = True,
    recent_messages: Sequence[BaseMessage] | None = None,
    mem0_memories: Sequence[str] | None = None,
) -> str:
    """Record a skipped rewrite span (no LLM) and return trimmed user text."""
    del rewrite_skip_reason, rewrite_skipped, recent_messages, mem0_memories
    return user_message.strip()


@rewrite_traceable()
def rewrite_query(
    user_message: str,
    mem0_text: str = "",
    recent_messages: Sequence[BaseMessage] | None = None,
    *,
    mem0_facts_count: int | None = None,
    model_name: str | None = None,
    rewrite_skipped: bool = False,
    rewrite_skip_reason: str = "",
) -> str:
    """
    Rewrite ``user_message`` using mem0 and short-term messages only.

    Does not read RAG results. On empty input or LLM failure, returns the
    trimmed original message.
    """
    del rewrite_skipped, rewrite_skip_reason
    del mem0_facts_count  # consumed by tracing metadata via process_inputs.
    original = user_message.strip()
    if not original:
        return ""

    recent = list(recent_messages or [])
    prompt = build_rewrite_prompt(original, mem0_text, recent)

    try:
        rewritten = _invoke_llm(prompt, model_name=model_name)
    except Exception:
        return original

    if not rewritten:
        return original
    return rewritten


def _extract_user_message(state: RewriteNodeState) -> str:
    if state.get("user_message"):
        return str(state["user_message"]).strip()

    messages = state.get("messages") or []
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            return str(message.content).strip()
    return ""


def rewrite_node(state: RewriteNodeState) -> dict[str, str]:
    """LangGraph node: set ``rewritten_query`` from mem0 + recent context."""
    user_message = _extract_user_message(state)
    mem0_memories = list(state.get("mem0_memories") or [])
    mem0_block = format_mem0_for_system(mem0_memories)
    recent_messages = state.get("recent_messages")
    if recent_messages is None:
        messages = state.get("messages") or []
        recent_messages = list(messages[:-1]) if messages else []
    else:
        recent_messages = list(recent_messages)

    settings = get_settings()
    use_skip = settings.REWRITE_SKIP_ENABLED and not settings.REWRITE_FORCE

    if use_skip:
        need_llm, reason = should_rewrite(
            user_message,
            recent_messages=recent_messages,
            mem0_memories=mem0_memories,
        )
        if not need_llm:
            rewritten = rewrite_passthrough(
                user_message,
                rewrite_skip_reason=reason,
                rewrite_skipped=True,
                recent_messages=recent_messages,
                mem0_memories=mem0_memories,
            )
            return {"rewritten_query": rewritten}

    rewritten = rewrite_query(
        user_message,
        mem0_text=mem0_block,
        recent_messages=recent_messages,
        mem0_facts_count=len(mem0_memories),
        rewrite_skipped=False,
        rewrite_skip_reason="",
    )
    return {"rewritten_query": rewritten}
