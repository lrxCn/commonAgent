"""Structured LLM intent classifier for low-confidence control-plane cases."""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError

from contracts.intent import (
    IntentDecision,
    IntentDomain,
    IntentOperation,
    IntentRisk,
    IntentRoute,
    SpeechAct,
)
from contracts.llm import ModelUseCase
from gateway.schemas import ToolSpec
from infrastructure.llm.gateway import LlmGateway, get_llm_gateway
from intent.conflicts import IntentConflictCheck, check_intent_conflicts
from intent.rules import decide_with_rules
from intent.signals import IntentSignals, extract_signals
from settings.config import Settings, get_settings

_classifier_override: BaseChatModel | Callable[[list[object]], object] | Callable[[str], str] | None = None


@dataclass(frozen=True)
class IntentClassifierResult:
    """Structured classifier output plus safety metadata."""

    decision: IntentDecision
    fallback: bool = False
    fallback_reason: str = ""
    repaired: bool = False
    conflict: IntentConflictCheck = IntentConflictCheck(has_conflict=False)

    @property
    def candidate(self) -> IntentDecision:
        """Alias emphasizing that this decision has no execution authority."""
        return self.decision


def set_intent_classifier_llm(
    llm: BaseChatModel | Callable[[list[object]], object] | Callable[[str], str] | None,
) -> None:
    """Replace classifier model for tests. Pass None to clear."""
    global _classifier_override
    _classifier_override = llm


def should_call_intent_classifier(
    *,
    rule_decision: IntentDecision,
    signals: IntentSignals,
    min_confidence: float = 0.8,
) -> bool:
    """Return whether low-confidence or conflicted rules should ask the model."""
    if rule_decision.confidence < min_confidence:
        return True
    return check_intent_conflicts(
        signals=signals,
        candidate=rule_decision,
        rule_decision=rule_decision,
    ).has_conflict


def classify_intent_with_llm(
    message: str,
    *,
    tools_context: Sequence[ToolSpec | dict[str, Any]] | None = None,
    rule_decision: IntentDecision | None = None,
    settings: Settings | None = None,
    gateway: LlmGateway | None = None,
) -> IntentClassifierResult:
    """
    Return a structured LLM intent candidate with schema and conflict checks.

    The returned decision is only a candidate for later Policy Gate tasks. This
    function does not write memory, execute tools, or alter graph routing.
    """
    signals = extract_signals(message, tools_context=tools_context)
    rules = rule_decision or decide_with_rules(signals)
    resolved_settings = settings or get_settings()
    resolved_gateway = gateway or get_llm_gateway(resolved_settings)
    system_prompt = build_intent_classifier_system_prompt()
    user_prompt = build_intent_classifier_user_prompt(
        signals=signals,
        tools_context=tools_context,
        rule_decision=rules,
    )

    try:
        raw = _invoke_classifier(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            gateway=resolved_gateway,
        )
        decision = parse_intent_decision(raw)
        conflict = check_intent_conflicts(
            signals=signals,
            candidate=decision,
            rule_decision=rules,
        )
        if conflict.has_conflict:
            return IntentClassifierResult(
                decision=_fallback_decision(signals, conflict.fallback_route, conflict.fallback_reason),
                fallback=True,
                fallback_reason=conflict.fallback_reason,
                conflict=conflict,
            )
        return IntentClassifierResult(decision=decision, conflict=conflict)
    except ValidationError as exc:
        try:
            raw = _invoke_repair(
                invalid_output=raw if "raw" in locals() else "",
                error=str(exc),
                gateway=resolved_gateway,
            )
            decision = parse_intent_decision(raw)
            conflict = check_intent_conflicts(
                signals=signals,
                candidate=decision,
                rule_decision=rules,
            )
            if conflict.has_conflict:
                return IntentClassifierResult(
                    decision=_fallback_decision(signals, conflict.fallback_route, conflict.fallback_reason),
                    fallback=True,
                    fallback_reason=conflict.fallback_reason,
                    repaired=True,
                    conflict=conflict,
                )
            return IntentClassifierResult(
                decision=decision,
                repaired=True,
                conflict=conflict,
            )
        except Exception as repair_exc:
            return IntentClassifierResult(
                decision=_fallback_decision(signals, None, "schema_invalid"),
                fallback=True,
                fallback_reason=_fallback_exception_reason(repair_exc, default="schema_invalid"),
                repaired=True,
            )
    except Exception as exc:
        return IntentClassifierResult(
            decision=_fallback_decision(signals, None, _fallback_exception_reason(exc)),
            fallback=True,
            fallback_reason=_fallback_exception_reason(exc),
        )


def build_intent_classifier_system_prompt() -> str:
    """Return the strict structured-output instruction for intent candidates."""
    schema = json.dumps(IntentDecision.model_json_schema(), ensure_ascii=False)
    return (
        "你是意图分类器，只输出一个 JSON object，不输出 Markdown。\n"
        "这个 JSON 只是候选，不拥有执行权，不能触发记忆写入或客户端工具。\n"
        "必须遵守 JSON Schema，字段包含 confidence、risk、reasons、evidence。\n"
        "遇到不确定或高风险冲突时选择 ambiguous/general_chat/clarify 倾向。\n"
        f"JSON Schema: {schema}"
    )


def build_intent_classifier_user_prompt(
    *,
    signals: IntentSignals,
    tools_context: Sequence[ToolSpec | dict[str, Any]] | None,
    rule_decision: IntentDecision,
) -> str:
    """Build compact classifier context from signals and deterministic rule output."""
    return json.dumps(
        {
            "user_message": signals.normalized_text,
            "signals": _signals_payload(signals),
            "allowed_tools": _tool_names(tools_context),
            "deterministic_rule": rule_decision.model_dump(mode="json"),
            "allowed_routes": [route.value for route in IntentRoute],
            "allowed_operations": [operation.value for operation in IntentOperation],
        },
        ensure_ascii=False,
    )


def parse_intent_decision(raw: str) -> IntentDecision:
    """Parse and validate a model-emitted IntentDecision JSON object."""
    text = raw.strip()
    try:
        return IntentDecision.model_validate_json(text)
    except ValidationError:
        extracted = _extract_json_object(text)
        if extracted == text:
            raise
        return IntentDecision.model_validate_json(extracted)


def _invoke_classifier(
    *,
    system_prompt: str,
    user_prompt: str,
    gateway: LlmGateway,
) -> str:
    if _classifier_override is not None:
        if hasattr(_classifier_override, "invoke"):
            response = _classifier_override.invoke(
                [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
            )
            return str(response.content).strip()
        try:
            response = _classifier_override([system_prompt, user_prompt])  # type: ignore[operator]
        except TypeError:
            response = _classifier_override(user_prompt)  # type: ignore[operator]
        return str(response).strip()

    llm = gateway.chat_model(ModelUseCase.INTENT_CLASSIFIER)
    response = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)])
    return str(response.content).strip()


def _invoke_repair(*, invalid_output: str, error: str, gateway: LlmGateway) -> str:
    repair_prompt = json.dumps(
        {
            "task": "Repair the invalid output into exactly one JSON object matching the IntentDecision schema.",
            "invalid_output": invalid_output,
            "validation_error": error,
        },
        ensure_ascii=False,
    )
    return _invoke_classifier(
        system_prompt=build_intent_classifier_system_prompt(),
        user_prompt=repair_prompt,
        gateway=gateway,
    )


def _fallback_decision(
    signals: IntentSignals,
    route: IntentRoute | None,
    reason: str,
) -> IntentDecision:
    fallback_route = route or IntentRoute.GENERAL_CHAT
    if signals.is_empty or signals.is_continuation:
        fallback_route = IntentRoute.AMBIGUOUS
    if signals.safety_reasons:
        fallback_route = IntentRoute.SAFETY_REFUSAL
    if fallback_route == IntentRoute.SAFETY_REFUSAL:
        return IntentDecision(
            speech_act=SpeechAct.UNSAFE,
            domain=IntentDomain.SAFETY,
            operation=IntentOperation.REJECT,
            route=IntentRoute.SAFETY_REFUSAL,
            confidence=0.2,
            risk=IntentRisk.HIGH,
            reasons=[reason or "classifier_fallback"],
            evidence=[signals.normalized_text or "input"],
        )
    if fallback_route == IntentRoute.AMBIGUOUS:
        return IntentDecision(
            speech_act=SpeechAct.UNCLEAR,
            domain=IntentDomain.UNKNOWN,
            operation=IntentOperation.CLARIFY,
            route=IntentRoute.AMBIGUOUS,
            confidence=0.2,
            risk=IntentRisk.MEDIUM,
            reasons=[reason or "classifier_fallback"],
            evidence=[signals.normalized_text or "input"],
            needs_clarification=True,
        )
    if fallback_route == IntentRoute.MEMORY_QUERY:
        return IntentDecision(
            speech_act=SpeechAct.QUESTION,
            domain=IntentDomain.USER_MEMORY,
            operation=IntentOperation.MEMORY_READ,
            route=IntentRoute.MEMORY_QUERY,
            confidence=0.2,
            risk=IntentRisk.MEDIUM,
            reasons=[reason or "classifier_fallback"],
            evidence=[signals.normalized_text or "input"],
        )
    return IntentDecision(
        speech_act=SpeechAct.QUESTION if signals.is_question else SpeechAct.STATEMENT,
        domain=IntentDomain.OPEN_CHAT,
        operation=IntentOperation.ANSWER,
        route=IntentRoute.GENERAL_CHAT,
        confidence=0.2,
        risk=IntentRisk.LOW,
        reasons=[reason or "classifier_fallback"],
        evidence=[signals.normalized_text or "input"],
    )


def _fallback_exception_reason(exc: Exception, *, default: str = "provider_error") -> str:
    name = type(exc).__name__
    if "timeout" in name.lower():
        return "timeout"
    if isinstance(exc, ValidationError):
        return default
    return name or default


def _extract_json_object(text: str) -> str:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return text
    return text[start : end + 1]


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


def _signals_payload(signals: IntentSignals) -> dict[str, object]:
    return {
        "is_question": signals.is_question,
        "is_command": signals.is_command,
        "is_first_person": signals.is_first_person,
        "is_org_self_reference": signals.is_org_self_reference,
        "fact_attributes": list(signals.fact_attributes),
        "explicit_values": list(signals.explicit_values),
        "has_knowledge_signal": signals.has_knowledge_signal,
        "has_tool_action": signals.has_tool_action,
        "has_allowed_client_tool": signals.has_allowed_client_tool,
        "has_anaphora": signals.has_anaphora,
        "is_continuation": signals.is_continuation,
        "safety_reasons": list(signals.safety_reasons),
    }
