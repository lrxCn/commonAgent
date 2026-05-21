"""Supervisor prompt budgeting tests."""

from __future__ import annotations

import pytest

from gateway.schemas import ToolSpec
from graph.supervisor import format_external_tools_for_prompt
from settings.config import Settings, reset_settings, set_settings_override

_REQUIRED_ENV = {
    "LANGSMITH_API_KEY": "lsv2_test",
    "OPENAI_API_KEY": "sk-test",
    "DATABASE_URL": "postgresql://postgres:test@localhost:5432/common_agent",
}


@pytest.fixture(autouse=True)
def _reset_settings_override() -> None:
    reset_settings()
    yield
    reset_settings()


def test_format_external_tools_for_prompt_caps_schema_budget() -> None:
    set_settings_override(
        Settings(  # type: ignore[arg-type]
            **_REQUIRED_ENV,
            TOOLS_SCHEMA_MAX_CHARS=180,
            _env_file=None,
        )
    )
    tool = ToolSpec(
        name="createApproval",
        description="Create a workflow approval.",
        parameters={
            "type": "object",
            "properties": {
                f"field_{index}": {"type": "string", "description": "x" * 40}
                for index in range(20)
            },
        },
        requires_approval=True,
    )

    block = format_external_tools_for_prompt([tool])

    assert len(block) <= 180
    assert "createApproval" in block
    assert "parameters schema" in block
    assert "field_19" not in block
