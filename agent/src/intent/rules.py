"""High-confidence deterministic intent rules."""

from __future__ import annotations

from contracts.intent import (
    IntentDecision,
    IntentDomain,
    IntentOperation,
    IntentRisk,
    IntentRoute,
    SpeechAct,
)
from graph.jump_page_catalog import extract_jump_page_slug
from intent.signals import IntentSignals, extract_signals


def decide_with_rules(signals: IntentSignals) -> IntentDecision:
    """Classify intent from extracted signals without LLM calls or graph state."""
    text = signals.normalized_text
    if signals.is_empty:
        return _decision(
            speech_act=SpeechAct.UNCLEAR,
            domain=IntentDomain.OPEN_CHAT,
            operation=IntentOperation.ANSWER,
            route=IntentRoute.GENERAL_CHAT,
            confidence=0.4,
            risk=IntentRisk.LOW,
            reasons=["empty"],
            evidence=[],
        )

    if signals.safety_reasons:
        return _decision(
            speech_act=SpeechAct.UNSAFE,
            domain=IntentDomain.SAFETY,
            operation=IntentOperation.REJECT,
            route=IntentRoute.SAFETY_REFUSAL,
            confidence=0.96,
            risk=IntentRisk.HIGH,
            reasons=list(signals.safety_reasons),
            evidence=_evidence(text, signals.safety_reasons),
        )

    if signals.is_chitchat:
        reason = signals.chitchat_kind or "chitchat"
        return _decision(
            speech_act=SpeechAct.CHITCHAT,
            domain=IntentDomain.OPEN_CHAT,
            operation=IntentOperation.ANSWER,
            route=IntentRoute.CHITCHAT,
            confidence=0.95,
            risk=IntentRisk.LOW,
            reasons=[reason],
            evidence=[text],
        )

    if _is_pure_client_action(signals):
        return _decision(
            speech_act=SpeechAct.COMMAND,
            domain=IntentDomain.CLIENT_TOOL,
            operation=IntentOperation.CLIENT_ACTION,
            route=IntentRoute.CLIENT_ACTION,
            confidence=0.93,
            risk=IntentRisk.LOW,
            reasons=["tool_command", "allowed_tool_available"],
            evidence=_client_action_evidence(signals),
        )

    if _is_memory_query(signals):
        return _memory_query_decision(signals)

    if _is_ambiguous(signals):
        reasons = ["continuation_without_anchor"] if signals.is_continuation else [
            "anaphora_without_anchor",
            "missing_target_domain",
        ]
        return _decision(
            speech_act=SpeechAct.UNCLEAR if signals.is_continuation else _speech_act(signals),
            domain=IntentDomain.UNKNOWN,
            operation=IntentOperation.CLARIFY,
            route=IntentRoute.AMBIGUOUS,
            confidence=0.78,
            risk=IntentRisk.MEDIUM,
            reasons=reasons,
            evidence=[text],
            needs_clarification=True,
        )

    if _is_fact_update(signals):
        return _fact_update_decision(signals)

    if _is_knowledge_query(signals):
        return _decision(
            speech_act=_speech_act(signals),
            domain=IntentDomain.KNOWLEDGE_BASE,
            operation=IntentOperation.KB_RETRIEVE,
            route=IntentRoute.KNOWLEDGE_QUERY,
            confidence=0.9,
            risk=IntentRisk.LOW,
            reasons=_knowledge_reasons(signals),
            evidence=_knowledge_evidence(signals),
        )

    if signals.has_tool_action and not signals.has_allowed_client_tool:
        return _decision(
            speech_act=SpeechAct.COMMAND,
            domain=IntentDomain.OPEN_CHAT,
            operation=IntentOperation.ANSWER,
            route=IntentRoute.GENERAL_CHAT,
            confidence=0.58,
            risk=IntentRisk.LOW,
            reasons=["tool_command_without_allowed_tool"],
            evidence=[text],
        )

    return _decision(
        speech_act=_speech_act(signals),
        domain=IntentDomain.OPEN_CHAT,
        operation=IntentOperation.ANSWER,
        route=IntentRoute.GENERAL_CHAT,
        confidence=0.62,
        risk=IntentRisk.LOW,
        reasons=["open_ended_generation" if signals.is_command else "default_general_chat"],
        evidence=[_general_evidence(text)],
    )


def classify_intent_with_rules(message: str, *, tools_context: object = None) -> IntentDecision:
    """Compatibility helper for callers that want rules without importing signals."""
    return decide_with_rules(extract_signals(message, tools_context=tools_context))  # type: ignore[arg-type]


def _is_pure_client_action(signals: IntentSignals) -> bool:
    return (
        signals.has_tool_action
        and signals.has_allowed_client_tool
        and (signals.has_page_reference or len(signals.normalized_text) <= 32)
        and not signals.has_knowledge_signal
    )


def _is_memory_query(signals: IntentSignals) -> bool:
    if not signals.is_question:
        return False
    if signals.is_first_person and _has_memory_target(signals):
        return True
    if "我是谁" in signals.normalized_text:
        return True
    return signals.is_org_self_reference and _has_company_memory_question(signals)


def _has_memory_target(signals: IntentSignals) -> bool:
    attrs = set(signals.fact_attributes)
    text = signals.normalized_text
    return bool(
        {"name", "birthday", "age", "city", "job", "company", "address", "preference"} & attrs
        or "我是谁" in text
        or "叫什么" in text
        or "喜欢什么" in text
        or "做什么" in text
    )


def _has_company_memory_question(signals: IntentSignals) -> bool:
    text = signals.normalized_text
    return bool("address" in signals.fact_attributes or "在哪" in text or "哪里" in text)


def _is_ambiguous(signals: IntentSignals) -> bool:
    return signals.is_continuation or (signals.has_anaphora and not signals.is_first_person)


def _is_fact_update(signals: IntentSignals) -> bool:
    if signals.is_question:
        return False
    if not signals.has_explicit_value:
        return False
    if not signals.fact_attributes:
        return False
    return signals.is_first_person or signals.is_org_self_reference or signals.legacy_user_fact_signal


def _is_knowledge_query(signals: IntentSignals) -> bool:
    if signals.is_first_person and signals.is_question and _has_memory_target(signals):
        return False
    return signals.has_knowledge_signal and not signals.is_chitchat


def _fact_update_decision(signals: IntentSignals) -> IntentDecision:
    domain = IntentDomain.ORG_MEMORY if signals.is_org_self_reference else IntentDomain.USER_MEMORY
    reasons = ["org_self_reference" if domain is IntentDomain.ORG_MEMORY else "first_person_fact_statement"]
    reasons.append(_explicit_value_reason(signals))
    return _decision(
        speech_act=SpeechAct.STATEMENT,
        domain=domain,
        operation=IntentOperation.MEMORY_WRITE,
        route=IntentRoute.FACT_UPDATE,
        confidence=0.94,
        risk=IntentRisk.LOW,
        reasons=reasons,
        evidence=_fact_evidence(signals),
    )


def _memory_query_decision(signals: IntentSignals) -> IntentDecision:
    domain = IntentDomain.ORG_MEMORY if signals.is_org_self_reference else IntentDomain.USER_MEMORY
    reasons = ["org_self_reference"] if domain is IntentDomain.ORG_MEMORY else ["first_person_question"]
    reasons.append(_memory_target_reason(signals))
    return _decision(
        speech_act=SpeechAct.QUESTION,
        domain=domain,
        operation=IntentOperation.MEMORY_READ,
        route=IntentRoute.MEMORY_QUERY,
        confidence=0.94,
        risk=IntentRisk.LOW,
        reasons=reasons,
        evidence=[signals.normalized_text],
    )


def _speech_act(signals: IntentSignals) -> SpeechAct:
    if signals.is_question:
        return SpeechAct.QUESTION
    if signals.is_command:
        return SpeechAct.COMMAND
    return SpeechAct.STATEMENT


def _explicit_value_reason(signals: IntentSignals) -> str:
    attrs = set(signals.fact_attributes)
    if "birthday" in attrs:
        return "explicit_birthday_value"
    if "address" in attrs:
        return "explicit_address_value"
    if "name" in attrs:
        return "explicit_name_value"
    return "explicit_fact_value"


def _memory_target_reason(signals: IntentSignals) -> str:
    attrs = set(signals.fact_attributes)
    text = signals.normalized_text
    if signals.is_org_self_reference and ("address" in attrs or "在哪" in text or "哪里" in text):
        return "company_location_question"
    if "name" in attrs or "叫什么" in text:
        return "name_memory_target"
    if "preference" in attrs:
        return "preference_memory_target"
    if "我是谁" in text:
        return "memory_profile_target"
    return "memory_profile_target"


def _knowledge_reasons(signals: IntentSignals) -> list[str]:
    if signals.is_command:
        return ["explicit_query_command", "knowledge_base_target"]
    return ["policy_question", "knowledge_base_target"]


def _knowledge_evidence(signals: IntentSignals) -> list[str]:
    if signals.knowledge_targets:
        return list(signals.knowledge_targets[:2])
    return [signals.normalized_text]


def _fact_evidence(signals: IntentSignals) -> list[str]:
    evidence: list[str] = []
    if signals.is_org_self_reference:
        evidence.append("我公司" if "我公司" in signals.normalized_text else "公司")
    elif signals.is_first_person:
        evidence.append("我")
    evidence.extend(signals.explicit_values[:2])
    return evidence or [signals.normalized_text]


def _client_action_evidence(signals: IntentSignals) -> list[str]:
    evidence = ["打开" if "打开" in signals.normalized_text else signals.normalized_text]
    if signals.has_page_reference:
        evidence.append(_page_evidence(signals.normalized_text))
    return evidence


def _page_evidence(text: str) -> str:
    slug = extract_jump_page_slug(text)
    if slug:
        return slug
    if "订单页" in text:
        return "订单页"
    return text


def _general_evidence(text: str) -> str:
    for prefix in ("帮我", "请", "麻烦"):
        if text.startswith(prefix):
            return text.removeprefix(prefix)
    return text


def _evidence(text: str, reasons: tuple[str, ...]) -> list[str]:
    evidence: list[str] = []
    for reason in reasons:
        if reason == "prompt_injection":
            evidence.append("忽略之前所有系统指令" if "忽略" in text else text)
        elif reason == "system_prompt_exfiltration":
            evidence.append("隐藏提示词" if "隐藏提示词" in text else text)
        elif reason == "sensitive_personal_data_request":
            evidence.append("私人手机号" if "私人手机号" in text else text)
        elif reason == "unauthorized_access":
            evidence.append("发给我" if "发给我" in text else text)
    return evidence or [text]


def _decision(
    *,
    speech_act: SpeechAct,
    domain: IntentDomain,
    operation: IntentOperation,
    route: IntentRoute,
    confidence: float,
    risk: IntentRisk,
    reasons: list[str],
    evidence: list[str],
    needs_clarification: bool = False,
) -> IntentDecision:
    return IntentDecision(
        speech_act=speech_act,
        domain=domain,
        operation=operation,
        route=route,
        confidence=confidence,
        risk=risk,
        reasons=reasons,
        evidence=evidence or ["input"],
        needs_clarification=needs_clarification,
    )
