"""Tests for the central LLM gateway and model policy."""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import pytest

from contracts.llm import ModelUseCase
from infrastructure.llm.gateway import (
    fallback_rerank_scores,
    get_llm_gateway,
    parse_rerank_scores,
)
from settings.config import Settings, reset_settings

_REQUIRED_ENV = {
    "LANGSMITH_API_KEY": "lsv2_test",
    "OPENAI_API_KEY": "sk-test",
    "DATABASE_URL": "postgresql://postgres:test@localhost:5432/common_agent",
}


@pytest.fixture(autouse=True)
def _clean_settings() -> None:
    reset_settings()
    yield
    reset_settings()


def _settings(**extra: object) -> Settings:
    return Settings(**{**_REQUIRED_ENV, **extra})  # type: ignore[arg-type]


def test_chat_policy_resolves_each_use_case() -> None:
    settings = _settings(
        OPENAI_MODEL_NAME="main-model",
        REWRITE_MODEL_NAME="rewrite-model",
        REWRITE_MAX_TOKENS=42,
        REWRITE_TIMEOUT_SECONDS=3.5,
        RAG_ROUTER_MODEL_NAME="router-model",
        RAG_ROUTER_MAX_TOKENS=12,
        RAG_ROUTER_TIMEOUT_SECONDS=2.5,
        CHITCHAT_MODEL_NAME="chat-small",
        CHITCHAT_MAX_TOKENS=9,
        CHITCHAT_TIMEOUT_SECONDS=1.5,
        MEM0_LLM_MODEL_NAME="mem0-small",
        MEM0_LLM_MAX_TOKENS=96,
        MEM0_LLM_TIMEOUT_SECONDS=4.5,
        INTENT_CLASSIFIER_MODEL_NAME="intent-small",
        INTENT_CLASSIFIER_MAX_TOKENS=144,
        INTENT_CLASSIFIER_TIMEOUT_SECONDS=2.25,
    )
    gateway = get_llm_gateway(settings)

    rewrite = gateway.chat_policy(ModelUseCase.REWRITE)
    router = gateway.chat_policy(ModelUseCase.ROUTER)
    chitchat = gateway.chat_policy(ModelUseCase.CHITCHAT)
    mem0 = gateway.chat_policy(ModelUseCase.MEM0_WRITE)
    intent = gateway.chat_policy(ModelUseCase.INTENT_CLASSIFIER)
    main = gateway.chat_policy(ModelUseCase.MAIN_ANSWER, streaming=True)

    assert (rewrite.model_name, rewrite.max_tokens, rewrite.timeout_seconds) == (
        "rewrite-model",
        42,
        3.5,
    )
    assert (router.model_name, router.max_tokens, router.timeout_seconds) == (
        "router-model",
        12,
        2.5,
    )
    assert (chitchat.model_name, chitchat.max_tokens, chitchat.timeout_seconds) == (
        "chat-small",
        9,
        1.5,
    )
    assert (mem0.model_name, mem0.max_tokens, mem0.timeout_seconds) == (
        "mem0-small",
        96,
        4.5,
    )
    assert (intent.model_name, intent.max_tokens, intent.timeout_seconds) == (
        "intent-small",
        144,
        2.25,
    )
    assert main.model_name == "main-model"
    assert main.streaming is True


def test_chat_model_uses_policy_kwargs(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(REWRITE_MODEL_NAME="rewrite-model", REWRITE_MAX_TOKENS=7)
    captured: dict[str, object] = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

    monkeypatch.setattr("infrastructure.llm.clients.ChatOpenAI", FakeChatOpenAI)

    model = get_llm_gateway(settings).chat_model(ModelUseCase.REWRITE)

    assert isinstance(model, FakeChatOpenAI)
    assert captured["model"] == "rewrite-model"
    assert captured["max_completion_tokens"] == 7
    assert captured["max_retries"] == 0


def test_streaming_chat_model_installs_callback(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings()
    captured: dict[str, object] = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

    class Callback:
        def __init__(self, sink: object) -> None:
            self.sink = sink

    monkeypatch.setattr("infrastructure.llm.clients.ChatOpenAI", FakeChatOpenAI)

    def sink(token: str) -> str:
        return token

    get_llm_gateway(settings).chat_model(
        ModelUseCase.MAIN_ANSWER,
        streaming=True,
        token_sink=sink,
        callback_factory=Callback,  # type: ignore[arg-type]
    )

    assert captured["streaming"] is True
    callbacks = captured["callbacks"]
    assert isinstance(callbacks, list)
    assert callbacks[0].sink is sink


def test_embedding_gateway_uses_embedding_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(EMBEDDING_MODEL="embed-model", EMBEDDING_MODEL_DIMS=256)
    captured: dict[str, object] = {}

    class FakeEmbeddings:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

        def embed_query(self, query: str) -> list[float]:
            return [float(len(query))]

    monkeypatch.setattr("infrastructure.llm.clients.OpenAIEmbeddings", FakeEmbeddings)

    vector = get_llm_gateway(settings).embed_query("abc")

    assert vector == [3.0]
    assert captured["model"] == "embed-model"
    assert captured["dimensions"] == 256


def test_parse_rerank_scores_and_fallback() -> None:
    assert parse_rerank_scores(
        {"results": [{"index": 1, "relevance_score": 0.9}, {"index": 0, "score": 0.2}]},
        document_count=2,
    ) == [0.2, 0.9]
    assert parse_rerank_scores({"bad": []}, document_count=3) == [3.0, 2.0, 1.0]
    assert fallback_rerank_scores(2) == [2.0, 1.0]


def test_rerank_gateway_uses_timeout_and_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(RERANK_MODEL="rerank-model")
    captured: dict[str, object] = {}

    class FakeClient:
        def __init__(self, *, timeout: float) -> None:
            captured["timeout"] = timeout

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def post(self, *args: object, **kwargs: object) -> MagicMock:
            captured["url"] = args[0]
            captured["json"] = kwargs["json"]
            raise httpx.TimeoutException("slow")

    monkeypatch.setattr("infrastructure.llm.gateway.httpx.Client", FakeClient)

    scores = get_llm_gateway(settings).rerank("q", ["a", "b"])

    assert scores == [2.0, 1.0]
    assert captured["timeout"] == 30
    assert captured["json"]["model"] == "rerank-model"
