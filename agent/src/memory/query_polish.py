"""Small-model polish for memory_query deterministic replies."""

from __future__ import annotations

from collections.abc import Callable

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from contracts.llm import ModelUseCase
from contracts.memory_query_polish import (
    MemoryQueryPolishInput,
    MemoryQueryPolishResult,
    polish_validation_failed,
    validate_polish_output,
)
from infrastructure.llm.gateway import LlmGateway, get_llm_gateway
from settings.config import Settings, get_settings

_llm_override: BaseChatModel | Callable[[list[object]], object] | Callable[[str], str] | None = None


def set_memory_query_polish_llm(
    llm: BaseChatModel | Callable[[list[object]], object] | Callable[[str], str] | None,
) -> None:
    """Replace polish LLM for tests. Pass None to clear."""
    global _llm_override
    _llm_override = llm


def build_polish_system_prompt() -> str:
    """System constraints: wording only, preserve evidence values, no new facts."""
    return (
        "你是 memory_query 话术生成器。你只能根据输入的 evidence 回答用户问题，不能增删或修改事实。"
        "必须保留 evidence 中每个 value 的原文。"
        "如果没有 evidence，不得猜测或编造用户信息，只能诚实说明缺失。"
        "用一句简短、自然、口语化的中文回复，像助手在正常对话。"
        "禁止使用「我记录到」「根据可靠记忆」等机械模板句式。"
        "不要输出解释、JSON 或 Markdown，只输出一句中文回复。"
        "不要使用“可能”“大概”“我猜”“不确定”等不确定表述。"
    )


def build_polish_user_prompt(polish_input: MemoryQueryPolishInput) -> str:
    """Serialize question and evidence for the polish model (draft is fallback-only, not shown)."""
    evidence_lines = [
        f"- field={item.field}, value={item.value}, source={item.source}, note={item.text}"
        for item in polish_input.evidence
    ]
    evidence_block = "\n".join(evidence_lines) if evidence_lines else "- none"
    missing = polish_input.missing_reason or "none"
    return (
        f"question: {polish_input.question}\n"
        f"missing_reason: {missing}\n"
        f"evidence:\n{evidence_block}\n"
        "请只输出一句自然的中文回复："
    )


def _invoke_polish_llm(
    polish_input: MemoryQueryPolishInput,
    *,
    settings: Settings,
    gateway: LlmGateway,
    model_name: str | None = None,
) -> str:
    messages = [
        SystemMessage(content=build_polish_system_prompt()),
        HumanMessage(content=build_polish_user_prompt(polish_input)),
    ]
    if _llm_override is not None:
        if hasattr(_llm_override, "invoke"):
            response = _llm_override.invoke(messages)
            return str(response.content).strip()
        return str(_llm_override(messages)).strip()  # type: ignore[operator]

    llm = gateway.chat_model(
        ModelUseCase.MEMORY_QUERY_POLISH,
        model_name=model_name,
    )
    response = llm.invoke(messages)
    return str(response.content).strip()


def polish_memory_query_reply(
    polish_input: MemoryQueryPolishInput,
    *,
    settings: Settings | None = None,
    gateway: LlmGateway | None = None,
    use_llm: bool | None = None,
    model_name: str | None = None,
) -> MemoryQueryPolishResult:
    """Polish deterministic memory_query draft; fallback to draft on disable or failure."""
    draft = polish_input.draft_reply
    resolved_settings = settings or get_settings()
    enabled = (
        resolved_settings.MEMORY_QUERY_POLISH_USE_LLM if use_llm is None else bool(use_llm)
    )

    if not enabled:
        return MemoryQueryPolishResult(
            reply=draft,
            used_llm=False,
            fallback_reason="disabled",
            changed=False,
        )

    resolved_gateway = gateway or get_llm_gateway(resolved_settings)
    try:
        raw = _invoke_polish_llm(
            polish_input,
            settings=resolved_settings,
            gateway=resolved_gateway,
            model_name=model_name,
        )
    except Exception as exc:
        return MemoryQueryPolishResult(
            reply=draft,
            used_llm=True,
            fallback_reason=type(exc).__name__,
            changed=False,
        )

    max_chars = max(len(draft) * 2, resolved_settings.MEMORY_QUERY_POLISH_MAX_TOKENS * 4)
    ok, reason = validate_polish_output(
        raw,
        draft_reply=draft,
        evidence=polish_input.evidence,
        missing_reason=polish_input.missing_reason,
        max_chars=max_chars,
    )
    if not ok:
        return MemoryQueryPolishResult(
            reply=draft,
            used_llm=True,
            fallback_reason=reason,
            changed=False,
        )

    return MemoryQueryPolishResult(
        reply=raw,
        used_llm=True,
        fallback_reason="",
        changed=raw != draft,
    )


def memory_query_polish_trace_metadata(
    *,
    enabled: bool,
    outcome: MemoryQueryPolishResult,
    model_name: str = "",
) -> dict[str, object]:
    """Flatten polish audit fields for path metrics and LangSmith metadata."""
    called = bool(enabled and outcome.used_llm)
    return {
        "memory_query.polish.enabled": enabled,
        "memory_query.polish.called": called,
        "memory_query.polish.model": model_name if called else "",
        "memory_query.polish.changed": outcome.changed,
        "memory_query.polish.fallback_reason": outcome.fallback_reason,
        "memory_query.polish.validation_failed": polish_validation_failed(outcome.fallback_reason),
    }
