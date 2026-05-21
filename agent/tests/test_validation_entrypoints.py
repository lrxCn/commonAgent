"""Validation entrypoint tests for local developer commands."""

from __future__ import annotations

from pathlib import Path


AGENT_ROOT = Path(__file__).resolve().parents[1]


def _makefile_target_body(target: str) -> str:
    lines = (AGENT_ROOT / "Makefile").read_text(encoding="utf-8").splitlines()
    start = lines.index(f"{target}:") + 1
    body: list[str] = []
    for line in lines[start:]:
        if line and not line.startswith("\t") and line.endswith(":"):
            break
        if line.startswith("\t"):
            body.append(line.strip())
    return "\n".join(body)


def test_make_test_points_at_current_tests_directory() -> None:
    body = _makefile_target_body("test")

    assert "pytest tests" in body
    assert "not integration" in body
    assert (AGENT_ROOT / "tests").is_dir()
    assert any((AGENT_ROOT / "tests").glob("test_*.py"))


def test_make_integration_tests_uses_existing_marker() -> None:
    body = _makefile_target_body("integration-tests")
    pyproject = (AGENT_ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert "pytest tests" in body
    assert "-m integration" in body
    assert "integration: requires live Postgres at DATABASE_URL" in pyproject
