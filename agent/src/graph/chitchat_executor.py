"""Lightweight executor for chitchat turns."""

from __future__ import annotations

from collections.abc import Callable
from functools import lru_cache
from typing import TypedDict

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage

from contracts.llm import ModelUseCase
from infrastructure.llm.gateway import get_llm_gateway
from observability.tracing import attach_run_metadata, chitchat_traceable
from settings.config import get_settings

_llm_override: BaseChatModel | Callable[[str], str] | None = None


class ChitchatResult(TypedDict):
    reply: str
    executor: str


def set_chitchat_llm(llm: BaseChatModel | Callable[[str], str] | None) -> None:
    """Replace the LLM used by chitchat_reply (tests). Pass None to clear."""
    global _llm_override
    _llm_override = llm


@lru_cache
def _template_pairs() -> tuple[tuple[str, str], ...]:
    return (
        ("谢谢", "不客气。"),
        ("多谢", "不客气。"),
        ("辛苦了", "应该的。"),
        ("你好", "你好。"),
        ("您好", "您好。"),
        ("早上好", "早上好。"),
        ("中午好", "中午好。"),
        ("下午好", "下午好。"),
        ("晚上好", "晚上好。"),
        ("拜拜", "回头见。"),
        ("再见", "回头见。"),
        ("好的", "好。"),
        ("好", "好。"),
        ("嗯", "嗯。"),
        ("收到", "收到。"),
        ("ok", "好。"),
        ("okay", "好。"),
        ("hello", "你好。"),
        ("hi", "你好。"),
        ("thanks", "不客气。"),
        ("thank you", "不客气。"),
        ("bye", "回头见。"),
    )


def _normalize(text: str) -> str:
    normalized = str(text or "").strip().lower()
    for ch in "。．.!！?？~～,，;；:：":
        normalized = normalized.replace(ch, "")
    return normalized


def _template_reply(user_message: str) -> str:
    normalized = _normalize(user_message)
    for key, reply in _template_pairs():
        if normalized == key:
            return reply
    return "嗯，我在。"


def _call_metadata(model_name: str | None, prompt: str) -> dict[str, object]:
    try:
        metadata = get_llm_gateway().metadata(
            ModelUseCase.CHITCHAT,
            model_name=model_name,
        )
    except Exception:
        return {
            "executor": "small_chat_executor",
            "chitchat.model_name": model_name or "override",
            "chitchat.prompt_len": len(prompt),
        }
    return {
        "llm.use_case": metadata.use_case.value,
        "executor": "small_chat_executor",
        "chitchat.model_name": metadata.model_name,
        "chitchat.prompt_len": len(prompt),
        "chitchat.max_tokens": metadata.max_tokens,
        "chitchat.timeout_seconds": metadata.timeout_seconds,
    }


def _build_prompt(user_message: str) -> str:
    return (
        "你是一个轻量寒暄回复器。"
        "请直接回复用户的寒暄、感谢或简单确认，语气自然、简短，不要扩展话题，不要调用工具，不要编造事实。"
        f"\n用户：{user_message.strip()}\n助手："
    )


def _invoke_llm(prompt: str, *, model_name: str | None = None) -> str:
    if _llm_override is not None:
        if hasattr(_llm_override, "invoke"):
            response = _llm_override.invoke([HumanMessage(content=prompt)])
            return str(response.content).strip()
        return str(_llm_override(prompt)).strip()  # type: ignore[operator]

    settings = get_settings()
    llm = get_llm_gateway(settings).chat_model(
        ModelUseCase.CHITCHAT,
        model_name=model_name,
    )
    response = llm.invoke([HumanMessage(content=prompt)])
    return str(response.content).strip()


@chitchat_traceable()
def chitchat_reply(
    user_message: str,
    *,
    use_llm: bool | None = None,
    model_name: str | None = None,
) -> ChitchatResult:
    """Return a lightweight chitchat reply using template or small LLM."""
    settings = get_settings()
    enabled = settings.CHITCHAT_USE_LLM if use_llm is None else bool(use_llm)
    text = str(user_message or "").strip()

    if not enabled:
        reply = _template_reply(text)
        attach_run_metadata(
            {
                "executor": "template_executor",
                "chitchat.use_llm": False,
                "chitchat.fallback": False,
            }
        )
        return {"reply": reply, "executor": "template_executor"}

    prompt = _build_prompt(text)
    attach_run_metadata(
        {
            **_call_metadata(model_name, prompt),
            "chitchat.use_llm": True,
        }
    )
    try:
        reply = _invoke_llm(prompt, model_name=model_name)
    except Exception as exc:
        fallback = _template_reply(text)
        attach_run_metadata(
            {
                "executor": "template_executor",
                "chitchat.use_llm": True,
                "chitchat.fallback": True,
                "chitchat.fallback_reason": type(exc).__name__,
            }
        )
        return {"reply": fallback, "executor": "template_executor"}

    if not reply:
        fallback = _template_reply(text)
        attach_run_metadata(
            {
                "executor": "template_executor",
                "chitchat.use_llm": True,
                "chitchat.fallback": True,
                "chitchat.fallback_reason": "empty_output",
            }
        )
        return {"reply": fallback, "executor": "template_executor"}

    attach_run_metadata(
        {
            "executor": "small_chat_executor",
            "chitchat.use_llm": True,
            "chitchat.fallback": False,
        }
    )
    return {"reply": reply, "executor": "small_chat_executor"}
