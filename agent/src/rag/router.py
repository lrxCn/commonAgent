"""RAG routing: rule-first, optional LLM classification (hybrid mode)."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Sequence
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, TypedDict

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage

from gateway.schemas import ToolSpec
from observability.tracing import attach_run_metadata, rag_router_traceable
from rag.intent import has_knowledge_intent, is_chitchat, is_user_fact_statement
from settings.config import Settings, get_settings

_PROMPT_PATH = Path(__file__).parent / "prompts" / "router_classify.txt"

_classifier_override: BaseChatModel | Callable[[str], str] | None = None

# --- Rule patterns (client-tool / navigation) ---

_NAV_INTENT_RE = re.compile(
    r"(?:打开|跳转|前往|进入|切换到|去|open|goto|go\s+to|navigate)",
    re.IGNORECASE,
)

_PAGE_REF_RE = re.compile(
    r"(?:page[a-zA-Z0-9_\-]+|页面\s*[a-zA-Z0-9_\-]+|/[a-zA-Z0-9_\-/]+)",
    re.IGNORECASE,
)

_NAV_TOOL_NAMES = frozenset(
    {"jumppage", "jump_page", "navigate", "navigatetopage", "openpage", "open_page"}
)


class RuleDecision(str, Enum):
    SKIP = "skip"
    RETRIEVE = "retrieve"
    UNCERTAIN = "uncertain"


class RagRouterNodeState(TypedDict, total=False):
    """Minimal state slice for rag_router_node."""

    user_message: str
    message: str
    rewritten_query: str
    tools: list[ToolSpec]
    tools_context: list[ToolSpec]
    rag_skipped: bool


def set_router_classifier(
    llm: BaseChatModel | Callable[[str], str] | None,
) -> None:
    """Replace hybrid classifier LLM (tests). Pass None to clear."""
    global _classifier_override
    _classifier_override = llm


@lru_cache
def _load_classifier_prompt_template() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _text(value: str | None) -> str:
    return (value or "").strip()


def _tool_names(tools_context: Sequence[ToolSpec | dict[str, Any]] | None) -> list[str]:
    if not tools_context:
        return []
    names: list[str] = []
    for item in tools_context:
        if isinstance(item, ToolSpec):
            names.append(item.name)
        elif isinstance(item, dict) and item.get("name"):
            names.append(str(item["name"]))
    return names


def _has_navigation_tool(tools_context: Sequence[ToolSpec | dict[str, Any]] | None) -> bool:
    for name in _tool_names(tools_context):
        normalized = name.strip().lower().replace("-", "_")
        if normalized in _NAV_TOOL_NAMES or "jump" in normalized or "navigate" in normalized:
            return True
    return False


def is_pure_client_tool_intent(
    message: str,
    tools_context: Sequence[ToolSpec | dict[str, Any]] | None,
    *,
    rewritten_query: str | None = None,
) -> bool:
    """
    Navigation-only intent with whitelisted client tools and no knowledge ask.

    Example: 「打开 pageA」 + jumpPage → skip RAG.
    """
    if not _has_navigation_tool(tools_context):
        return False
    if has_knowledge_intent(message, rewritten_query):
        return False

    for text in (_text(message), _text(rewritten_query)):
        if not text:
            continue
        if _NAV_INTENT_RE.search(text) and (
            _PAGE_REF_RE.search(text) or len(text) <= 32
        ):
            return True
    return False


def classify_with_rules(
    message: str,
    rewritten_query: str | None = None,
    tools_context: Sequence[ToolSpec | dict[str, Any]] | None = None,
) -> RuleDecision:
    """Apply deterministic routing rules."""
    if is_chitchat(message, rewritten_query):
        return RuleDecision.SKIP
    if is_user_fact_statement(message, rewritten_query):
        return RuleDecision.SKIP
    if has_knowledge_intent(message, rewritten_query):
        return RuleDecision.RETRIEVE
    if is_pure_client_tool_intent(message, tools_context, rewritten_query=rewritten_query):
        return RuleDecision.SKIP
    return RuleDecision.UNCERTAIN


def build_router_classifier_prompt(
    message: str,
    rewritten_query: str | None,
    tools_context: Sequence[ToolSpec | dict[str, Any]] | None,
) -> str:
    template = _load_classifier_prompt_template()
    names = _tool_names(tools_context)
    tool_names = ", ".join(names) if names else "（无）"
    return template.format(
        message=_text(message) or "（空）",
        rewritten_query=_text(rewritten_query) or _text(message) or "（空）",
        tool_names=tool_names,
    )


def parse_need_rag_json(raw: str) -> bool | None:
    """Parse ``{"need_rag": true/false}`` from classifier output."""
    text = raw.strip()
    if not text:
        return None
    try:
        data = json.loads(text)
        if isinstance(data, dict) and "need_rag" in data:
            return bool(data["need_rag"])
    except json.JSONDecodeError:
        pass

    fence = re.search(r"\{[^{}]*\"need_rag\"\s*:\s*(true|false)[^{}]*\}", text, re.I)
    if fence:
        try:
            data = json.loads(fence.group(0))
            return bool(data.get("need_rag"))
        except json.JSONDecodeError:
            return None
    return None


def _create_classifier_model(settings: Settings, model_name: str | None) -> BaseChatModel:
    from langchain_openai import ChatOpenAI

    name = _resolve_model_name(settings, model_name)
    return ChatOpenAI(
        model=name,
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL,
        temperature=0,
        max_completion_tokens=settings.RAG_ROUTER_MAX_TOKENS,
        timeout=settings.RAG_ROUTER_TIMEOUT_SECONDS,
        max_retries=0,
    )


def _resolve_model_name(settings: Settings, model_name: str | None) -> str:
    return (
        model_name
        or settings.RAG_ROUTER_MODEL_NAME
        or settings.OPENAI_MODEL_NAME
    ).strip()


def _call_metadata(
    model_name: str | None,
    prompt: str,
    mode: Literal["rules", "hybrid"] | None,
) -> dict[str, object]:
    try:
        settings = get_settings()
    except Exception:
        return {
            "rag_router.model_name": model_name or "override",
            "rag_router.prompt_len": len(prompt),
            "rag_router.mode": mode,
        }
    return {
        "rag_router.model_name": _resolve_model_name(settings, model_name),
        "rag_router.prompt_len": len(prompt),
        "rag_router.mode": mode or settings.RAG_ROUTER_MODE,
        "rag_router.max_tokens": settings.RAG_ROUTER_MAX_TOKENS,
        "rag_router.timeout_seconds": settings.RAG_ROUTER_TIMEOUT_SECONDS,
    }


def _invoke_classifier(prompt: str, *, model_name: str | None = None) -> str:
    if _classifier_override is not None:
        if hasattr(_classifier_override, "invoke"):
            response = _classifier_override.invoke([HumanMessage(content=prompt)])
            return str(response.content).strip()
        return str(_classifier_override(prompt)).strip()  # type: ignore[operator]

    settings = get_settings()
    llm = _create_classifier_model(settings, model_name)
    response = llm.invoke([HumanMessage(content=prompt)])
    return str(response.content).strip()


def classify_with_llm(
    message: str,
    rewritten_query: str | None = None,
    tools_context: Sequence[ToolSpec | dict[str, Any]] | None = None,
    *,
    model_name: str | None = None,
    mode: Literal["rules", "hybrid"] | None = None,
) -> bool:
    """Hybrid fallback: small LLM emits JSON ``need_rag``."""
    prompt = build_router_classifier_prompt(message, rewritten_query, tools_context)
    attach_run_metadata(_call_metadata(model_name, prompt, mode))
    try:
        raw = _invoke_classifier(prompt, model_name=model_name)
        parsed = parse_need_rag_json(raw)
        if parsed is not None:
            attach_run_metadata({"rag_router.fallback": False})
            return parsed
        attach_run_metadata(
            {
                "rag_router.fallback": True,
                "rag_router.fallback_reason": "parse_failed",
            }
        )
    except Exception as exc:
        attach_run_metadata(
            {
                "rag_router.fallback": True,
                "rag_router.fallback_reason": type(exc).__name__,
            }
        )
    # Conservative default when classifier fails
    return True


@rag_router_traceable()
def should_retrieve(
    message: str,
    rewritten_query: str | None = None,
    tools_context: Sequence[ToolSpec | dict[str, Any]] | None = None,
    *,
    mode: Literal["rules", "hybrid"] | None = None,
) -> bool:
    """
    Whether this turn should run RAG retrieval.

    Rules first; in hybrid mode, uncertain cases use an LLM classifier.
    """
    settings = get_settings()
    router_mode: Literal["rules", "hybrid"] = mode or settings.RAG_ROUTER_MODE  # type: ignore[assignment]

    decision = classify_with_rules(message, rewritten_query, tools_context)
    if decision is RuleDecision.SKIP:
        attach_run_metadata(
            {
                "rag_router.mode": router_mode,
                "rag_router.rule_decision": decision.value,
                "rag_router.fallback": False,
            }
        )
        return False
    if decision is RuleDecision.RETRIEVE:
        attach_run_metadata(
            {
                "rag_router.mode": router_mode,
                "rag_router.rule_decision": decision.value,
                "rag_router.fallback": False,
            }
        )
        return True
    if router_mode == "rules":
        attach_run_metadata(
            {
                "rag_router.mode": router_mode,
                "rag_router.rule_decision": decision.value,
                "rag_router.fallback": False,
            }
        )
        return True
    attach_run_metadata(
        {
            "rag_router.mode": router_mode,
            "rag_router.rule_decision": decision.value,
        }
    )
    return classify_with_llm(message, rewritten_query, tools_context, mode=router_mode)


def rag_router_node(state: RagRouterNodeState) -> dict[str, bool]:
    """LangGraph node: set ``rag_skipped`` when retrieval should be skipped."""
    message = _text(state.get("user_message")) or _text(state.get("message"))
    rewritten = state.get("rewritten_query")
    tools = state.get("tools_context") or state.get("tools")

    need_rag = should_retrieve(message, rewritten, tools)
    return {"rag_skipped": not need_rag}
