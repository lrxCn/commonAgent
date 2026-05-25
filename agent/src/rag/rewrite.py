"""Query rewrite using user memories + short-term context (no RAG)."""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from functools import lru_cache
from pathlib import Path
from typing import TypedDict

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from contracts.events import ObservabilityEventType
from contracts.llm import ModelUseCase
from infrastructure.llm.gateway import get_llm_gateway
from memory.formatting import format_user_memories_for_system
from observability.tracing import emit_event, rewrite_traceable
from rag.intent import has_knowledge_intent, is_chitchat, is_user_fact_statement
from settings.config import get_settings

_PROMPT_PATH = Path(__file__).parent / "prompts" / "rewrite.txt"

_llm_override: BaseChatModel | Callable[[str], str] | None = None

_ANAPHORA_RE = re.compile(
    r"(?:它|这个|那个|上述|刚才|继续|还有吗|后者|前者|这般|那样|如此|同上|前述)",
    re.IGNORECASE,
)

_NUMBER_RE = re.compile(r"\d+(?:[./:-]\d+)*")


class RewriteNodeState(TypedDict, total=False):
    """Minimal state slice for rewrite_node (full AgentState comes in task 13)."""

    user_message: str
    turn_type: str
    user_memories: list[str]
    recent_messages: list[BaseMessage]
    messages: list[BaseMessage]
    policy_fast_path_allowed: bool
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
    user_memories_text: str,
    recent_messages: Sequence[BaseMessage],
) -> str:
    """Fill the rewrite prompt template (user memories + short-term only; no RAG)."""
    template = _load_prompt_template()
    user_memories_block = user_memories_text.strip() if user_memories_text.strip() else "（无）"
    return template.format(
        user_message=user_message.strip(),
        user_memories_text=user_memories_block,
        recent_messages_text=format_recent_messages(recent_messages),
    )


def _has_anaphora(message: str) -> bool:
    return _ANAPHORA_RE.search(message.strip()) is not None


def _numbers(text: str) -> list[str]:
    return _NUMBER_RE.findall(text)


def _rewrite_preserves_numbers(original: str, rewritten: str) -> bool:
    original_numbers = _numbers(original)
    if not original_numbers:
        return True
    return original_numbers == _numbers(rewritten)


def should_rewrite(
    user_message: str,
    *,
    recent_messages: Sequence[BaseMessage],
    user_memories: Sequence[str] | None = None,
    turn_type: str | None = None,
    policy_denied_fact_update: bool = False,
) -> tuple[bool, str]:
    """
    Return ``(need_llm_rewrite, reason_code)``.

    ``reason_code`` is for tracing only; when ``need_llm_rewrite`` is False the
    caller must not invoke the rewrite LLM.
    """
    text = user_message.strip()
    if not text:
        return False, "empty"

    if policy_denied_fact_update:
        return True, "policy_denied_fact_update"

    normalized_turn_type = (turn_type or "").strip()
    if normalized_turn_type in {
        "fact_update",
        "chitchat",
        "client_action",
        "knowledge_query",
        "general_chat",
    }:
        return False, f"turn_type_{normalized_turn_type}"
    if normalized_turn_type == "ambiguous":
        return True, "turn_type_ambiguous"

    if is_chitchat(text):
        return False, "chitchat"

    if not _has_anaphora(text) and is_user_fact_statement(text):
        return False, "personal_fact_statement"

    settings = get_settings()
    min_len = settings.REWRITE_MIN_SELF_CONTAINED_LEN
    memories = list(user_memories or [])
    recent = list(recent_messages or [])
    has_user_memories = bool(memories)
    has_recent = bool(recent)

    if not has_recent and not has_user_memories:
        if not _has_anaphora(text) and len(text) >= min_len:
            return False, "standalone_no_context"

    if (
        not _has_anaphora(text)
        and len(text) >= min_len
        and has_knowledge_intent(text)
    ):
        return False, "self_contained"

    return True, "needs_disambiguation"


def _call_metadata(model_name: str | None, prompt: str) -> dict[str, object]:
    try:
        metadata = get_llm_gateway().metadata(
            ModelUseCase.REWRITE,
            model_name=model_name,
        )
    except Exception:
        return {
            "rewrite.model_name": model_name or "override",
            "rewrite.prompt_len": len(prompt),
        }
    return {
        "llm.use_case": metadata.use_case.value,
        "rewrite.model_name": metadata.model_name,
        "rewrite.prompt_len": len(prompt),
        "rewrite.max_tokens": metadata.max_tokens,
        "rewrite.timeout_seconds": metadata.timeout_seconds,
    }


def _invoke_llm(prompt: str, *, model_name: str | None = None) -> str:
    if _llm_override is not None:
        if hasattr(_llm_override, "invoke"):
            response = _llm_override.invoke([HumanMessage(content=prompt)])
            return str(response.content).strip()
        return str(_llm_override(prompt)).strip()  # type: ignore[operator]

    settings = get_settings()
    llm = get_llm_gateway(settings).chat_model(
        ModelUseCase.REWRITE,
        model_name=model_name,
    )
    response = llm.invoke([HumanMessage(content=prompt)])
    return str(response.content).strip()


@rewrite_traceable()
def rewrite_passthrough(
    user_message: str,
    *,
    rewrite_skip_reason: str,
    rewrite_skipped: bool = True,
    recent_messages: Sequence[BaseMessage] | None = None,
    user_memories: Sequence[str] | None = None,
) -> str:
    """Record a skipped rewrite span (no LLM) and return trimmed user text."""
    del recent_messages, user_memories
    emit_event(
        ObservabilityEventType.REWRITE_SKIPPED,
        {
            "rewrite_skipped": rewrite_skipped,
            "rewrite_skip_reason": rewrite_skip_reason,
            "rewrite.fallback": False,
        }
    )
    return user_message.strip()


@rewrite_traceable()
def rewrite_query(
    user_message: str,
    user_memories_text: str = "",
    recent_messages: Sequence[BaseMessage] | None = None,
    *,
    user_memory_facts_count: int | None = None,
    model_name: str | None = None,
    rewrite_skipped: bool = False,
    rewrite_skip_reason: str = "",
) -> str:
    """
    Rewrite ``user_message`` using user memories and short-term messages only.

    Does not read RAG results. On empty input or LLM failure, returns the
    trimmed original message.
    """
    del user_memory_facts_count  # consumed by tracing metadata via process_inputs.
    original = user_message.strip()
    if not original:
        return ""

    recent = list(recent_messages or [])
    prompt = build_rewrite_prompt(original, user_memories_text, recent)
    emit_event(
        ObservabilityEventType.LLM_CALL_COMPLETED,
        {
            **_call_metadata(model_name, prompt),
            "rewrite_skipped": rewrite_skipped,
            "rewrite_skip_reason": rewrite_skip_reason,
        }
    )

    try:
        rewritten = _invoke_llm(prompt, model_name=model_name)
    except Exception as exc:
        emit_event(
            ObservabilityEventType.REWRITE_COMPLETED,
            {
                "rewrite.fallback": True,
                "rewrite.fallback_reason": type(exc).__name__,
            }
        )
        return original

    if not rewritten:
        emit_event(
            ObservabilityEventType.REWRITE_COMPLETED,
            {
                "rewrite.fallback": True,
                "rewrite.fallback_reason": "empty_output",
            }
        )
        return original
    if not _rewrite_preserves_numbers(original, rewritten):
        emit_event(
            ObservabilityEventType.REWRITE_COMPLETED,
            {
                "rewrite.fallback": True,
                "rewrite.fallback_reason": "number_changed",
            }
        )
        return original
    emit_event(ObservabilityEventType.REWRITE_COMPLETED, {"rewrite.fallback": False})
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
    """LangGraph node: set ``rewritten_query`` from user memories + recent context."""
    user_message = _extract_user_message(state)
    user_memories = list(state.get("user_memories") or [])
    user_memories_block = format_user_memories_for_system(user_memories)
    recent_messages = state.get("recent_messages")
    if recent_messages is None:
        messages = state.get("messages") or []
        recent_messages = list(messages[:-1]) if messages else []
    else:
        recent_messages = list(recent_messages)

    settings = get_settings()
    use_skip = settings.REWRITE_SKIP_ENABLED and not settings.REWRITE_FORCE

    if use_skip:
        if (
            state.get("turn_type") == "fact_update"
            and state.get("policy_fast_path_allowed") is True
        ):
            rewritten = rewrite_passthrough(
                user_message,
                rewrite_skip_reason="policy_allowed_fact_update",
                rewrite_skipped=True,
                recent_messages=recent_messages,
                user_memories=user_memories,
            )
            return {"rewritten_query": rewritten}
        need_llm, reason = should_rewrite(
            user_message,
            recent_messages=recent_messages,
            user_memories=user_memories,
            turn_type=state.get("turn_type"),
            policy_denied_fact_update=bool(state.get("policy_denied_fact_update", False)),
        )
        if not need_llm:
            rewritten = rewrite_passthrough(
                user_message,
                rewrite_skip_reason=reason,
                rewrite_skipped=True,
                recent_messages=recent_messages,
                user_memories=user_memories,
            )
            return {"rewritten_query": rewritten}

    rewritten = rewrite_query(
        user_message,
        user_memories_text=user_memories_block,
        recent_messages=recent_messages,
        user_memory_facts_count=len(user_memories),
        rewrite_skipped=False,
        rewrite_skip_reason="",
    )
    return {"rewritten_query": rewritten}
