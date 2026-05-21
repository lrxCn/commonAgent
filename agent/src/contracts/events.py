"""Observability event contracts for future tracing decoupling."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ObservabilityEvent:
    """Small immutable domain event envelope."""

    name: str
    metadata: dict[str, Any] = field(default_factory=dict)
