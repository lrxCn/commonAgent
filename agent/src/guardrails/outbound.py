"""Outbound text guardrails (full-response check after Supervisor)."""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from guardrails.types import GuardResult
from observability.tracing import attach_run_metadata, outbound_guardrails_traceable

if TYPE_CHECKING:
    from settings.config import Settings

logger = logging.getLogger(__name__)

# Safe replacement when outbound policy blocks model output.
OUTBOUND_SAFE_REPLY = "抱歉，我无法提供该回复。请换一种方式提问。"

# Fixed patterns for leaked system instructions / policy bypass in model output.
_OUTBOUND_BLOCK_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"here\s+is\s+(the\s+)?(full\s+)?system\s+prompt", re.IGNORECASE),
    re.compile(r"my\s+system\s+prompt\s+is\s*:", re.IGNORECASE),
    re.compile(r"<\s*/?\s*system\s*>", re.IGNORECASE),
    re.compile(
        r"ignore\s+(all\s+)?(prior|previous)\s+instructions.*(?:i\s+will|here)",
        re.IGNORECASE,
    ),
)

# Stable marker for unit / graph tests (must match a rule above).
OUTBOUND_TEST_SAMPLE = (
    "Here is the full system prompt: You are a helpful enterprise assistant."
)

OptionalHook = Callable[[str], GuardResult | None]

_optional_hook: OptionalHook | None = None


@dataclass(frozen=True)
class StreamingOutboundDecision:
    """Incremental outbound moderation result for a streamed text window."""

    allowed: bool
    reason_code: str | None = None
    replacement: str | None = None


def register_outbound_hook(hook: OptionalHook | None) -> None:
    """Register optional LangChain/LangSmith template hook (returns None to defer to rules)."""
    global _optional_hook
    _optional_hook = hook


def _rule_check(text: str) -> GuardResult | None:
    normalized = text.strip()
    if not normalized:
        return None
    for pattern in _OUTBOUND_BLOCK_PATTERNS:
        if pattern.search(normalized):
            return GuardResult.block(
                reason_code="policy_violation",
                message=OUTBOUND_SAFE_REPLY,
            )
    return None


def record_outbound_block_event(
    *,
    reason_code: str,
    text_len: int,
    internal_error: bool = False,
) -> None:
    """Emit block metadata for LangSmith trace and application logs."""
    metadata: dict[str, Any] = {
        "guardrails.direction": "outbound",
        "guardrails.blocked": True,
        "guardrails.reason_code": reason_code,
        "guardrails.text_len": text_len,
        "guardrails.internal_error": internal_error,
    }
    attach_run_metadata(metadata)
    logger.warning("guardrails.outbound.blocked", extra=metadata)


@outbound_guardrails_traceable()
def check_outbound(text: str, *, settings: Settings | None = None) -> GuardResult:
    """Run outbound guardrails on full assistant reply text."""
    if settings is None:
        from settings.config import get_settings

        settings = get_settings()

    if not settings.GUARDRAILS_ENABLED:
        return GuardResult.pass_through()

    if _optional_hook is not None:
        try:
            hook_result = _optional_hook(text)
        except Exception:
            logger.exception("outbound guardrail hook failed")
            record_outbound_block_event(
                reason_code="internal_error",
                text_len=len(text),
                internal_error=True,
            )
            return GuardResult.block(
                reason_code="content_blocked",
                message=OUTBOUND_SAFE_REPLY,
            )
        if hook_result is not None:
            if not hook_result.allowed:
                record_outbound_block_event(
                    reason_code=hook_result.reason_code or "content_blocked",
                    text_len=len(text),
                )
            return hook_result

    blocked = _rule_check(text)
    if blocked is not None:
        record_outbound_block_event(
            reason_code=blocked.reason_code or "policy_violation",
            text_len=len(text),
        )
        return blocked

    return GuardResult.pass_through()


def check_outbound_stream_window(
    text: str,
    *,
    settings: Settings | None = None,
) -> StreamingOutboundDecision:
    """Check a streamed sentence/window and return retract/replace guidance."""
    result = check_outbound(text, settings=settings)
    if result.allowed:
        return StreamingOutboundDecision(allowed=True)
    return StreamingOutboundDecision(
        allowed=False,
        reason_code=result.reason_code or "outbound_guard",
        replacement=result.message or OUTBOUND_SAFE_REPLY,
    )
