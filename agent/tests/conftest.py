import os

import pytest


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def _disable_langsmith_export(monkeypatch: pytest.MonkeyPatch) -> None:
    """Avoid sending test runs to LangSmith (invalid keys → 403 noise)."""
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
