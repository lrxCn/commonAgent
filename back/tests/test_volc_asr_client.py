"""Unit tests for Volcengine SAUC upstream client."""

from __future__ import annotations

from services.volc_asr.client import VolcAsrClient
from settings.config import Settings


def _settings_with_asr(**overrides: object) -> Settings:
    base = {
        "AGENT_DATABASE_URL": "postgresql://postgres:secret@localhost:5432/common_agent",
        "SESSION_SECRET": "test",
        "VOLC_ASR_ACCESS_KEY": "test-api-key",
        "VOLC_ASR_RESOURCE_ID": "volc.seedasr.sauc.duration",
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def test_auth_headers_new_console() -> None:
    client = VolcAsrClient(
        _settings_with_asr(VOLC_ASR_APP_KEY="legacy-app-key-should-not-appear"),
    )
    headers = client._auth_headers()

    assert headers["X-Api-Key"] == "test-api-key"
    assert headers["X-Api-Sequence"] == "-1"
    assert headers["X-Api-Resource-Id"] == "volc.seedasr.sauc.duration"
    assert headers["X-Api-Request-Id"]
    assert "X-Api-Access-Key" not in headers
    assert "X-Api-App-Key" not in headers
