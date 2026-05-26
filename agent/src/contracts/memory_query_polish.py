"""Contracts for memory_query deterministic-draft polish (wording only)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from memory.query import MemoryQueryEvidence, MemoryQueryResult

_UNCERTAINTY_TOKENS = ("可能", "大概", "我猜", "不确定", "或许", "也许")
_MISSING_AFFIRMATIVE_PATTERNS = (
    "你叫",
    "你的名字是",
    "你出生于",
    "你公司在",
    "公司地址是",
    "你在",
    "你是",
)


@dataclass(frozen=True)
class MemoryQueryPolishInput:
    """Structured input for memory query polish; no raw memory store access."""

    question: str
    draft_reply: str
    evidence: tuple[MemoryQueryEvidence, ...]
    missing_reason: str = ""


@dataclass(frozen=True)
class MemoryQueryPolishResult:
    """Final reply after optional LLM polish with audit metadata."""

    reply: str
    used_llm: bool
    fallback_reason: str = ""
    changed: bool = False


def build_polish_input(question: str, result: MemoryQueryResult) -> MemoryQueryPolishInput:
    """Build polish input from deterministic memory query output."""
    return MemoryQueryPolishInput(
        question=str(question or "").strip(),
        draft_reply=result.reply,
        evidence=result.evidence,
        missing_reason=result.missing_reason,
    )


def validate_polish_output(
    output: str,
    *,
    draft_reply: str,
    evidence: Sequence[MemoryQueryEvidence],
    missing_reason: str,
    max_chars: int | None = None,
) -> tuple[bool, str]:
    """
    Validate polished wording against evidence and missing-memory constraints.

    Returns (ok, fallback_reason). fallback_reason is empty when ok is True.
    """
    text = str(output or "").strip()
    if not text:
        return False, "empty_output"

    limit = max_chars if max_chars is not None else max(len(draft_reply) * 2, 120)
    if len(text) > limit:
        return False, "too_long"

    for token in _UNCERTAINTY_TOKENS:
        if token in text:
            return False, "uncertain_fact_phrasing"

    for item in evidence:
        if item.value and item.value not in text:
            return False, "missing_evidence_value"

    if missing_reason:
        for pattern in _MISSING_AFFIRMATIVE_PATTERNS:
            if pattern in text:
                return False, "affirmative_fact_when_missing"

    return True, ""


POLISH_VALIDATION_FAILURE_REASONS = frozenset(
    {
        "empty_output",
        "too_long",
        "uncertain_fact_phrasing",
        "missing_evidence_value",
        "affirmative_fact_when_missing",
    }
)


def polish_validation_failed(fallback_reason: str) -> bool:
    """Return whether fallback_reason indicates output validation failure."""
    return fallback_reason in POLISH_VALIDATION_FAILURE_REASONS
