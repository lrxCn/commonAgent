"""State lifecycle guardrails for single-turn graph fields."""

from __future__ import annotations

from typing import Annotated, get_args, get_origin, get_type_hints

from langgraph.channels.ephemeral_value import EphemeralValue

from graph import nodes
from graph.state import AgentState


def _is_ephemeral_value(annotation: object) -> bool:
    if get_origin(annotation) is not Annotated:
        return False
    return any(metadata is EphemeralValue for metadata in get_args(annotation)[1:])


def test_ephemeral_state_fields_are_explicitly_carried_within_turn() -> None:
    """Every EphemeralValue field must be kept in sync with the node carry list."""
    annotations = get_type_hints(AgentState, include_extras=True)
    ephemeral_fields = {
        name for name, annotation in annotations.items() if _is_ephemeral_value(annotation)
    }
    carry_keys = set(nodes._EPHEMERAL_CARRY_KEYS)

    assert ephemeral_fields == carry_keys
    assert "messages" not in carry_keys


def test_carry_keys_are_known_agent_state_fields() -> None:
    annotations = get_type_hints(AgentState, include_extras=True)

    assert set(nodes._EPHEMERAL_CARRY_KEYS).issubset(annotations)
