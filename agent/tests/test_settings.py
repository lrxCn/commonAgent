"""Tests for settings.config — env loading and get_settings()."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from settings.config import Settings, get_settings, reset_settings, set_settings_override

_REQUIRED_ENV = {
    "LANGSMITH_API_KEY": "lsv2_test",
    "OPENAI_API_KEY": "sk-test",
    "DATABASE_URL": "postgresql://postgres:test@localhost:5432/common_agent",
}

_REPO_ROOT = Path(__file__).resolve().parents[1]
_ENV_CONTRACT_FILES = (
    _REPO_ROOT / ".env.example",
    _REPO_ROOT / ".env",
)


@pytest.fixture(autouse=True)
def _clean_settings_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate env and settings singleton between tests."""
    reset_settings()
    for key in list(_REQUIRED_ENV) + list(Settings.model_fields):
        monkeypatch.delenv(key, raising=False)
    yield
    reset_settings()


def _patch_required(monkeypatch: pytest.MonkeyPatch, **extra: str) -> None:
    for key, value in {**_REQUIRED_ENV, **extra}.items():
        monkeypatch.setenv(key, value)


def _settings(monkeypatch: pytest.MonkeyPatch, **extra: str) -> Settings:
    _patch_required(monkeypatch, **extra)
    return Settings(_env_file=None)


def _env_keys(path: Path) -> set[str]:
    keys: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key = stripped.split("=", 1)[0]
        if key and key.replace("_", "").isalnum() and key.upper() == key:
            keys.add(key)
    return keys


def test_loads_required_and_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(monkeypatch)
    assert settings.OPENAI_API_KEY == "sk-test"
    assert settings.EMBEDDING_MODEL_DIMS == 1024
    assert settings.AGENT_PORT == 18080
    assert settings.qdrant_url == "http://localhost:6333"
    assert settings.CONTEXT_PREFIX_TURNS == 4
    assert settings.CONTEXT_RECENT_TURNS == 20
    assert settings.CONTEXT_ORIGINAL_HUMAN_METADATA_KEY == "original_human_content"
    assert settings.REWRITE_MAX_TOKENS == 64
    assert settings.REWRITE_TIMEOUT_SECONDS == 15
    assert settings.CHITCHAT_USE_LLM is False
    assert settings.CHITCHAT_MAX_TOKENS == 48
    assert settings.CHITCHAT_TIMEOUT_SECONDS == 5
    assert settings.RAG_ROUTER_MAX_TOKENS == 32
    assert settings.RAG_ROUTER_TIMEOUT_SECONDS == 5


def test_env_files_match_settings_contract() -> None:
    settings_keys = set(Settings.model_fields)
    for path in _ENV_CONTRACT_FILES:
        assert _env_keys(path) == settings_keys


def test_qdrant_url_uses_host_and_port(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(monkeypatch, QDRANT_HOST="qdrant.internal", QDRANT_PORT="6334")
    assert settings.qdrant_url == "http://qdrant.internal:6334"


def test_langchain_api_key_falls_back_to_langsmith(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)
    settings = _settings(monkeypatch)
    assert settings.LANGCHAIN_API_KEY == settings.LANGSMITH_API_KEY


def test_langchain_api_key_env_takes_precedence(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(monkeypatch, LANGCHAIN_API_KEY="lc_explicit")
    assert settings.LANGCHAIN_API_KEY == "lc_explicit"


def test_missing_openai_api_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_required(monkeypatch)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)
    errors = exc_info.value.errors()
    assert any(e["loc"] == ("OPENAI_API_KEY",) for e in errors)


def test_missing_database_url_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_required(monkeypatch)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)
    errors = exc_info.value.errors()
    assert any(e["loc"] == ("DATABASE_URL",) for e in errors)


def test_get_settings_singleton_and_override(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_required(monkeypatch)
    first = get_settings()
    second = get_settings()
    assert first is second

    custom = Settings(
        LANGSMITH_API_KEY="lsv2_custom",
        OPENAI_API_KEY="sk-custom",
        DATABASE_URL=_REQUIRED_ENV["DATABASE_URL"],
        AGENT_PORT=9999,
    )
    set_settings_override(custom)
    assert get_settings().AGENT_PORT == 9999

    reset_settings()
    _patch_required(monkeypatch)
    assert get_settings().AGENT_PORT == 18080


def test_tracing_flag_parses_string(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(monkeypatch, LANGCHAIN_TRACING_V2="false")
    assert settings.LANGCHAIN_TRACING_V2 is False


def test_guardrails_enabled_defaults_true(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(monkeypatch)
    assert settings.GUARDRAILS_ENABLED is True


def test_guardrails_enabled_parses_string(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(monkeypatch, GUARDRAILS_ENABLED="false")
    assert settings.GUARDRAILS_ENABLED is False


def test_mem0_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(monkeypatch)
    assert settings.MEM0_MOCK is False
    assert settings.QDRANT_COLLECTION_MEM0 == "common_agent_mem0"
    assert settings.MEM0_READ_LIMIT == 50
    assert settings.MEM0_LLM_MODEL_NAME is None
    assert settings.MEM0_LLM_MAX_TOKENS == 128
    assert settings.MEM0_LLM_TIMEOUT_SECONDS == 10


def test_mem0_mock_parses_string(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(monkeypatch, MEM0_MOCK="false")
    assert settings.MEM0_MOCK is False


def test_qdrant_mock_defaults_false(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(monkeypatch)
    assert settings.QDRANT_MOCK is False


def test_qdrant_mock_parses_string(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(monkeypatch, QDRANT_MOCK="false")
    assert settings.QDRANT_MOCK is False


def test_small_task_model_limits_parse_env(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(
        monkeypatch,
        REWRITE_MAX_TOKENS="48",
        REWRITE_TIMEOUT_SECONDS="7.5",
        CHITCHAT_USE_LLM="true",
        CHITCHAT_MAX_TOKENS="24",
        CHITCHAT_TIMEOUT_SECONDS="2.5",
        RAG_ROUTER_MAX_TOKENS="16",
        RAG_ROUTER_TIMEOUT_SECONDS="3.25",
        MEM0_LLM_MODEL_NAME="Qwen/Qwen2.5-7B-Instruct",
        MEM0_LLM_MAX_TOKENS="96",
        MEM0_LLM_TIMEOUT_SECONDS="4.5",
    )
    assert settings.REWRITE_MAX_TOKENS == 48
    assert settings.REWRITE_TIMEOUT_SECONDS == 7.5
    assert settings.CHITCHAT_USE_LLM is True
    assert settings.CHITCHAT_MAX_TOKENS == 24
    assert settings.CHITCHAT_TIMEOUT_SECONDS == 2.5
    assert settings.RAG_ROUTER_MAX_TOKENS == 16
    assert settings.RAG_ROUTER_TIMEOUT_SECONDS == 3.25
    assert settings.MEM0_LLM_MODEL_NAME == "Qwen/Qwen2.5-7B-Instruct"
    assert settings.MEM0_LLM_MAX_TOKENS == 96
    assert settings.MEM0_LLM_TIMEOUT_SECONDS == 4.5
