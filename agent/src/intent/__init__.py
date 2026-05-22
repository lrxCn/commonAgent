"""Deterministic intent control-plane API."""

from intent.engine import classify_intent
from intent.rules import decide_with_rules
from intent.signals import IntentSignals, extract_signals, normalize_text

__all__ = [
    "IntentSignals",
    "classify_intent",
    "decide_with_rules",
    "extract_signals",
    "normalize_text",
]
