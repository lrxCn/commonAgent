"""Normalize free-form mem0 facts into a compact memory profile."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class MemoryProfile:
    name: str = ""
    birth_year: str = ""
    city: str = ""
    job: str = ""
    company_address: str = ""
    answer_style: str = ""

    def is_empty(self) -> bool:
        return not any(
            (
                self.name,
                self.birth_year,
                self.city,
                self.job,
                self.company_address,
                self.answer_style,
            )
        )


@dataclass(frozen=True)
class ProfileNormalization:
    profile: MemoryProfile
    residual_facts: list[str]


_TRAILING_PUNCT = "。.!！?？,，;； "

_NAME_PATTERNS = (
    re.compile(r"(?:我|用户|本人)?(?:的)?(?:名字|姓名|叫)\s*[：:是为]?\s*([\w\u4e00-\u9fff·.-]{2,32})"),
    re.compile(r"(?:用户名|用户姓名)\s*(?:是|为|叫|:|：)\s*([\w\u4e00-\u9fff·.-]{2,32})"),
)
_BIRTH_YEAR_PATTERNS = (
    re.compile(r"(?:出生于|生于|出生年份|出生年|出生)\s*(\d{4})\s*年?"),
    re.compile(r"(?:birth year|born in)\s*[:：]?\s*(\d{4})", re.IGNORECASE),
)
_CITY_PATTERNS = (
    re.compile(r"(?:我|用户|本人)?(?:生活在|住在|居住在|来自|所在城市是|城市是)\s*([\w\u4e00-\u9fff·.-]{2,40})"),
    re.compile(r"(?:city|lives in)\s*[:：]?\s*([\w\u4e00-\u9fff·.\-\s]{2,40})", re.IGNORECASE),
)
_JOB_PATTERNS = (
    re.compile(r"(?:我|用户|本人)?(?:是|职业是|工作是|岗位是|职位是|从事)\s*([\w\u4e00-\u9fff·.\-\s]{2,60})"),
    re.compile(r"(?:job|role|occupation)\s*[:：]?\s*([\w\u4e00-\u9fff·.\-\s]{2,60})", re.IGNORECASE),
)
_COMPANY_ADDRESS_PATTERNS = (
    re.compile(r"(?:我公司|我的公司|我们公司|公司|单位)(?:地址|所在地|位于|在)\s*[：:是为]?\s*([\w\u4e00-\u9fff·.\-#/号楼室栋街路巷弄\s]{3,80})"),
    re.compile(r"(?:company address|office address)\s*[:：]?\s*([\w\u4e00-\u9fff·.\-#/号楼室栋街路巷弄\s]{3,80})", re.IGNORECASE),
)
_ANSWER_STYLE_PATTERNS = (
    re.compile(r"(?:偏好|喜欢|希望)\s*(?:回答|回复|答案|简洁|详细)([\w\u4e00-\u9fff·.\-\s]{0,60})"),
    re.compile(r"(?:回答风格|回复风格|答案风格)\s*[:：是为]?\s*([\w\u4e00-\u9fff·.\-\s]{2,60})"),
    re.compile(r"(?:prefers?|answer style|response style)\s*[:：]?\s*([\w\u4e00-\u9fff·.\-\s]{2,60})", re.IGNORECASE),
)


def _clean_value(value: str) -> str:
    cleaned = str(value or "").strip().strip(_TRAILING_PUNCT)
    return re.sub(r"\s+", " ", cleaned)


def _extract_first(patterns: Iterable[re.Pattern[str]], fact: str) -> str:
    for pattern in patterns:
        match = pattern.search(fact)
        if match:
            value = _clean_value(match.group(1))
            if not value and "简洁" in match.group(0):
                return "简洁回答"
            if not value and "详细" in match.group(0):
                return "详细回答"
            return value
    return ""


def _classify_fact(fact: str) -> tuple[str, str]:
    text = _clean_value(fact)
    if not text:
        return "", ""

    if any(word in text for word in ("回答", "回复", "答案")):
        if "简洁" in text:
            return "answer_style", "简洁回答"
        if "详细" in text:
            return "answer_style", "详细回答"

    checks: tuple[tuple[str, Iterable[re.Pattern[str]]], ...] = (
        ("name", _NAME_PATTERNS),
        ("birth_year", _BIRTH_YEAR_PATTERNS),
        ("company_address", _COMPANY_ADDRESS_PATTERNS),
        ("city", _CITY_PATTERNS),
        ("job", _JOB_PATTERNS),
        ("answer_style", _ANSWER_STYLE_PATTERNS),
    )
    for field, patterns in checks:
        value = _extract_first(patterns, text)
        if value:
            return field, value
    return "", ""


def normalize_memory_profile(facts: Iterable[str]) -> ProfileNormalization:
    """Build a profile from mem0 facts, keeping latest categorized value."""
    values: dict[str, str] = {}
    consumed: set[int] = set()
    cleaned_facts = [_clean_value(fact) for fact in facts if _clean_value(fact)]

    for index, fact in enumerate(cleaned_facts):
        field, value = _classify_fact(fact)
        if field and value:
            values[field] = value
            consumed.add(index)

    profile = MemoryProfile(
        name=values.get("name", ""),
        birth_year=values.get("birth_year", ""),
        city=values.get("city", ""),
        job=values.get("job", ""),
        company_address=values.get("company_address", ""),
        answer_style=values.get("answer_style", ""),
    )
    residual = [
        fact
        for index, fact in enumerate(cleaned_facts)
        if index not in consumed
    ]
    return ProfileNormalization(profile=profile, residual_facts=_dedupe(residual))


def _dedupe(facts: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for fact in facts:
        normalized = fact.strip()
        key = normalized.lower()
        if normalized and key not in seen:
            seen.add(key)
            out.append(normalized)
    return out


def format_memory_profile_for_system(profile: MemoryProfile) -> str:
    """Format normalized memory profile for system prompt injection."""
    if profile.is_empty():
        return ""

    lines = ["## Memory profile", ""]
    if profile.name:
        lines.append(f"- profile.name: {profile.name}")
    if profile.birth_year:
        lines.append(f"- profile.birth_year: {profile.birth_year}")
    if profile.city:
        lines.append(f"- profile.city: {profile.city}")
    if profile.job:
        lines.append(f"- profile.job: {profile.job}")
    if profile.company_address:
        lines.append(f"- company.address: {profile.company_address}")
    if profile.answer_style:
        lines.append(f"- preference.answer_style: {profile.answer_style}")
    return "\n".join(lines)
