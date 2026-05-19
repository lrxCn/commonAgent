"""Shared guardrail result types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ReasonCode = Literal[
    "policy_violation",
    "injection_attempt",
    "content_blocked",
]

_DEFAULT_BLOCK_MESSAGE = "Message blocked by inbound guardrails."


@dataclass(frozen=True, slots=True)
class GuardResult:
    """Outcome of an inbound or outbound guardrail check."""

    allowed: bool
    reason_code: ReasonCode | None = None
    message: str | None = None

    @classmethod
    def pass_through(cls) -> GuardResult:
        return cls(allowed=True)

    @classmethod
    def block(
        cls,
        *,
        reason_code: ReasonCode = "policy_violation",
        message: str | None = None,
    ) -> GuardResult:
        return cls(
            allowed=False,
            reason_code=reason_code,
            message=message or _DEFAULT_BLOCK_MESSAGE,
        )
