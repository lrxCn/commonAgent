"""Deterministic answers for user memory read queries."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from langchain_core.messages import BaseMessage, HumanMessage

from memory.profile import MemoryProfile, normalize_memory_profile

MISSING_MEMORY_REPLY = "我目前没有可靠记录你是谁。你可以告诉我你的名字或身份，我之后会按你的授权记住。"


@dataclass(frozen=True)
class MemoryQueryEvidence:
    """A selected memory fact used by the memory query executor."""

    source: str
    field: str
    value: str
    text: str


@dataclass(frozen=True)
class MemoryQueryResult:
    """Reply plus audit metadata for a memory query turn."""

    reply: str
    evidence: tuple[MemoryQueryEvidence, ...]
    missing_reason: str = ""


_FIELD_LABELS = {
    "name": "姓名",
    "birth_year": "出生年份",
    "city": "城市",
    "job": "职业/身份",
    "company_address": "公司地址",
    "answer_style": "回答偏好",
}
_FIELD_REPLY_PREFIX = {
    "name": "我记录到你叫{value}。",
    "birth_year": "我记录到你的出生年份是 {value} 年。",
    "city": "我记录到你在{value}。",
    "job": "我记录到你是{value}。",
    "company_address": "我记录到你公司的地址是{value}。",
    "answer_style": "我记录到你偏好{value}。",
}
_TRAILING_PUNCT = "。.!！?？,，;； "


def answer_memory_query(
    question: str,
    *,
    user_memories: Sequence[str] | None = None,
    messages: Sequence[BaseMessage] | None = None,
) -> MemoryQueryResult:
    """Answer only from memory_profile, related mem0 free text, or prior user statements."""
    query = _clean(question)
    user_facts = [_clean(fact) for fact in user_memories or [] if _clean(fact)]
    history_facts = _thread_user_facts(messages or [])

    user_profile = normalize_memory_profile(user_facts)
    thread_profile = normalize_memory_profile(history_facts)
    requested = _requested_fields(query)

    evidence: list[MemoryQueryEvidence] = []
    for field in requested:
        item = _profile_evidence(user_profile.profile, field, "memory_profile")
        if item is None:
            item = _profile_evidence(thread_profile.profile, field, "thread_memory")
        if item is not None:
            evidence.append(item)

    if not evidence and _wants_preference(query):
        evidence.extend(_free_text_preference_evidence(user_profile.residual_facts, "memory_free_text"))
        if not evidence:
            evidence.extend(_free_text_preference_evidence(history_facts, "thread_memory"))

    if not evidence and _wants_profile(query):
        evidence.extend(_all_profile_evidence(user_profile.profile, "memory_profile"))
        if not evidence:
            evidence.extend(_all_profile_evidence(thread_profile.profile, "thread_memory"))

    if not evidence:
        return MemoryQueryResult(
            reply=_missing_reply_for_query(query),
            evidence=(),
            missing_reason=_missing_reason(query),
        )

    reply = _build_reply(query, evidence)
    return MemoryQueryResult(reply=reply, evidence=tuple(evidence))


def memory_query_trace_metadata(result: MemoryQueryResult) -> dict[str, object]:
    """Flatten memory query evidence for traces and tests."""
    return {
        "memory_query.evidence_count": len(result.evidence),
        "memory_query.evidence_sources": [item.source for item in result.evidence],
        "memory_query.evidence_fields": [item.field for item in result.evidence],
        "memory_query.missing_reason": result.missing_reason,
    }


def _clean(value: object | None) -> str:
    cleaned = str(value or "").strip().strip(_TRAILING_PUNCT)
    return re.sub(r"\s+", " ", cleaned)


def _requested_fields(query: str) -> list[str]:
    fields: list[str] = []
    if "叫什么" in query or "名字" in query or "姓名" in query:
        fields.append("name")
    if "生日" in query or "出生" in query or "年龄" in query:
        fields.append("birth_year")
    if ("公司" in query or "单位" in query) and ("在哪" in query or "哪里" in query or "地址" in query):
        fields.append("company_address")
    if "住哪" in query or "住在哪里" in query or "城市" in query or "来自哪里" in query:
        fields.append("city")
    if "做什么" in query or "职业" in query or "工作" in query or "职位" in query:
        fields.append("job")
    if _wants_preference(query):
        fields.append("answer_style")
    if fields:
        return list(dict.fromkeys(fields))
    if _wants_profile(query):
        return ["name", "job", "city", "birth_year", "company_address", "answer_style"]
    return []


def _wants_profile(query: str) -> bool:
    return "我是谁" in query or "我的身份" in query or not _requested_specific_target(query)


def _requested_specific_target(query: str) -> bool:
    return any(
        token in query
        for token in (
            "叫什么",
            "名字",
            "姓名",
            "生日",
            "出生",
            "年龄",
            "公司",
            "单位",
            "住哪",
            "城市",
            "来自哪里",
            "做什么",
            "职业",
            "工作",
            "职位",
            "喜欢",
            "偏好",
            "常用",
        )
    )


def _wants_preference(query: str) -> bool:
    return any(token in query for token in ("喜欢", "偏好", "常用", "不喜欢", "讨厌"))


def _profile_evidence(
    profile: MemoryProfile,
    field: str,
    source: str,
) -> MemoryQueryEvidence | None:
    value = _profile_value(profile, field)
    if not value:
        return None
    label = _FIELD_LABELS.get(field, field)
    return MemoryQueryEvidence(source=source, field=field, value=value, text=f"{label}: {value}")


def _all_profile_evidence(profile: MemoryProfile, source: str) -> list[MemoryQueryEvidence]:
    return [
        item
        for field in ("name", "job", "city", "birth_year", "company_address", "answer_style")
        if (item := _profile_evidence(profile, field, source)) is not None
    ]


def _profile_value(profile: MemoryProfile, field: str) -> str:
    return _clean(getattr(profile, field, ""))


def _free_text_preference_evidence(facts: Sequence[str], source: str) -> list[MemoryQueryEvidence]:
    evidence: list[MemoryQueryEvidence] = []
    for fact in facts:
        text = _clean(fact)
        if not text:
            continue
        if any(token in text for token in ("喜欢", "偏好", "常用", "不喜欢", "讨厌")):
            evidence.append(
                MemoryQueryEvidence(
                    source=source,
                    field="preference",
                    value=text,
                    text=text,
                )
            )
    return evidence[:3]


def _thread_user_facts(messages: Sequence[BaseMessage]) -> list[str]:
    facts: list[str] = []
    human_messages = [message for message in messages if isinstance(message, HumanMessage)]
    for message in human_messages[:-1]:
        text = _clean(message.content)
        if text:
            facts.append(text)
    return facts


def _build_reply(query: str, evidence: Sequence[MemoryQueryEvidence]) -> str:
    if len(evidence) == 1:
        item = evidence[0]
        template = _FIELD_REPLY_PREFIX.get(item.field)
        if template:
            return template.format(value=item.value)
        return f"我记录到：{item.value}。"

    if _wants_preference(query):
        facts = "；".join(item.value for item in evidence)
        return f"我记录到的相关偏好：{facts}。"

    facts = "；".join(_format_evidence_item(item) for item in evidence)
    return f"根据可靠记忆，我记录到：{facts}。"


def _format_evidence_item(item: MemoryQueryEvidence) -> str:
    if item.field == "name":
        return f"你叫{item.value}"
    if item.field == "birth_year":
        return f"出生年份是 {item.value} 年"
    if item.field == "city":
        return f"你在{item.value}"
    if item.field == "job":
        return f"你是{item.value}"
    if item.field == "company_address":
        return f"公司地址是{item.value}"
    if item.field == "answer_style":
        return f"回答偏好是{item.value}"
    return item.value


def _missing_reply_for_query(query: str) -> str:
    if "叫什么" in query or "名字" in query or "姓名" in query:
        return "我目前没有可靠记录你的姓名。你可以告诉我你的名字，我之后会按你的授权记住。"
    if "生日" in query or "出生" in query or "年龄" in query:
        return "我目前没有可靠记录你的生日或出生年份。你可以告诉我相关信息，我之后会按你的授权记住。"
    if "公司" in query or "单位" in query:
        return "我目前没有可靠记录你公司的地址。你可以告诉我公司地址，我之后会按你的授权记住。"
    if _wants_preference(query):
        return "我目前没有可靠记录你的相关偏好。你可以告诉我你的偏好，我之后会按你的授权记住。"
    return MISSING_MEMORY_REPLY


def _missing_reason(query: str) -> str:
    if _wants_profile(query):
        return "missing_memory_profile"
    fields = _requested_fields(query)
    if fields:
        return f"missing_{fields[0]}"
    return "missing_memory_profile"
