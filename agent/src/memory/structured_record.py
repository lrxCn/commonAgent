"""Deterministic slot fill from intent signals to structured memory records."""

from __future__ import annotations

import re

from contracts.intent import IntentDecision, IntentOperation, IntentRoute
from contracts.memory_write import ExtractionMethod, MemorySubject, StructuredMemoryRecord
from intent.signals import IntentSignals

_ATTRIBUTE_PRIORITY: tuple[str, ...] = (
    "name",
    "birthday",
    "age",
    "city",
    "job",
    "address",
    "phone",
    "email",
    "preference",
)

_NAME_VALUE_RE = re.compile(r"我叫\s*([\w\u4e00-\u9fff·.-]{1,32})")
_BIRTH_YEAR_VALUE_RE = re.compile(r"(?:出生于|生于|出生)\s*(\d{4})\s*年?")
_CITY_VALUE_RE = re.compile(
    r"(?:生活在|住在|居住在|来自|所在城市是|城市是)\s*([\w\u4e00-\u9fff·.-]{2,40})"
)
_JOB_VALUE_RE = re.compile(
    r"(?:职业是|工作是|岗位是|职位是|从事)\s*([\w\u4e00-\u9fff·.\-\s]{2,60})"
)
_COMPANY_ADDRESS_VALUE_RE = re.compile(
    r"(?:我公司|我的公司|我们公司|公司|单位)(?:地址|所在地|位于|在)\s*([\w\u4e00-\u9fff·.\-#/号楼室栋街路巷弄\s]{3,80})"
)
_PREFERENCE_VALUE_RE = re.compile(r"(?:喜欢|偏好|常用|不喜欢|讨厌)\s*([^，。！？?]{1,60})")
_YEAR_RE = re.compile(r"(\d{4})")


def build_structured_memory_record(
    signals: IntentSignals,
    intent_decision: IntentDecision,
    *,
    source_turn_id: str,
) -> StructuredMemoryRecord | None:
    """Map policy-ready intent signals to a deterministic structured memory record."""
    if not source_turn_id.strip():
        return None
    if not signals.fact_attributes or not signals.explicit_values:
        return None
    if signals.is_question:
        return None
    if _value(intent_decision.route) != IntentRoute.FACT_UPDATE.value:
        return None
    if _value(intent_decision.operation) != IntentOperation.MEMORY_WRITE.value:
        return None

    attribute = _select_record_attribute(signals)
    if attribute is None:
        return None

    value = _normalize_record_value(attribute, signals)
    if not value:
        return None

    subject = (
        MemorySubject.ORG
        if signals.is_org_self_reference and attribute == "company.address"
        else MemorySubject.USER
    )

    return StructuredMemoryRecord(
        subject=subject,
        attribute=attribute,
        value=value,
        raw_utterance=signals.original_text,
        confidence=float(intent_decision.confidence),
        source_turn_id=source_turn_id,
        extraction_method=ExtractionMethod.SLOT_FILL_V1.value,
    )


def canonical_fact_text(record: StructuredMemoryRecord) -> str:
    """Render stable canonical fact text for infer=False mem0 writes."""
    subject = _value(record.subject)
    attribute = record.attribute
    value = record.value

    if attribute == "name":
        return f"用户的名字是{value}"
    if attribute == "birthday":
        year = _birth_year_for_canonical(value)
        return f"用户出生于{year}年"
    if attribute == "city":
        return f"用户生活在{value}"
    if attribute == "job":
        return f"用户的职业是{value}"
    if attribute == "company.address":
        return f"公司地址是{value}"
    if attribute == "preference":
        canonical_value = value.replace("简短", "简洁")
        if any(token in canonical_value for token in ("回答", "回复", "答案", "简洁", "详细")):
            if "回答" not in canonical_value and (
                "简洁" in canonical_value or "详细" in canonical_value
            ):
                canonical_value = f"{canonical_value}回答"
            return f"用户喜欢{canonical_value}"
        return f"用户喜欢{value}"

    if subject == MemorySubject.ORG.value:
        return f"公司{attribute}是{value}"
    return f"用户{attribute}是{value}"


def _select_record_attribute(signals: IntentSignals) -> str | None:
    attrs = set(signals.fact_attributes)
    if signals.is_org_self_reference and ("address" in attrs or "company" in attrs):
        return "company.address"

    for attribute in _ATTRIBUTE_PRIORITY:
        if attribute in attrs:
            return attribute
    return None


def _normalize_record_value(attribute: str, signals: IntentSignals) -> str:
    text = signals.normalized_text
    explicit = signals.explicit_values

    if attribute == "name":
        match = _NAME_VALUE_RE.search(text)
        if match:
            return _clean_value(match.group(1))
        return _clean_value(explicit[0]) if explicit else ""

    if attribute == "birthday":
        match = _BIRTH_YEAR_VALUE_RE.search(text)
        if match:
            return match.group(1)
        for value in explicit:
            year_match = _YEAR_RE.search(value)
            if year_match:
                return year_match.group(1)
        return ""

    if attribute == "city":
        match = _CITY_VALUE_RE.search(text)
        if match:
            return _clean_value(match.group(1))
        return _clean_value(explicit[0]) if explicit else ""

    if attribute == "job":
        match = _JOB_VALUE_RE.search(text)
        if match:
            return _clean_value(match.group(1))
        return _clean_value(explicit[0]) if explicit else ""

    if attribute == "company.address":
        match = _COMPANY_ADDRESS_VALUE_RE.search(text)
        if match:
            return _clean_value(match.group(1))
        return _clean_value(explicit[0]) if explicit else ""

    if attribute == "preference":
        match = _PREFERENCE_VALUE_RE.search(text)
        if match:
            return _clean_value(match.group(1))
        return _clean_value(explicit[0]) if explicit else ""

    return _clean_value(explicit[0]) if explicit else ""


def _birth_year_for_canonical(value: str) -> str:
    match = _YEAR_RE.search(value)
    return match.group(1) if match else value


def _clean_value(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().strip("。.!！?？,，;； "))


def _value(value: object) -> str:
    return str(getattr(value, "value", value))
