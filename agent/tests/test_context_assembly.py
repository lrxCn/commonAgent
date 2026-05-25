"""Tests for memory.assembly — K + M + summary context assembly."""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from memory.assembly import (
    build_context,
    build_context_bundle,
    build_context_with_budget,
    build_system_prompt,
    build_system_prompt_with_budget,
    select_turn_index_ranges,
    split_into_turns,
)
from settings.config import Settings, get_settings, reset_settings, set_settings_override
from rag.retriever import RagChunk

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


def _turn(human: str, ai: str) -> list[HumanMessage | AIMessage]:
    return [HumanMessage(content=human), AIMessage(content=ai)]


def _history(
    turn_count: int,
    *,
    mark_middle_turns: bool = True,
) -> list[HumanMessage | AIMessage]:
    messages: list[HumanMessage | AIMessage] = []
    for i in range(1, turn_count + 1):
        if mark_middle_turns and 5 <= i <= 10:
            human = f"MIDDLE_T{i}"
        else:
            human = f"turn-{i}-human"
        messages.extend(_turn(human, f"turn-{i}-ai"))
    return messages


def test_select_turn_ranges_n30_k4_m20() -> None:
    prefix, middle, recent = select_turn_index_ranges(30, k=4, m=20)
    assert prefix == [0, 1, 2, 3]
    assert middle == [4, 5, 6, 7, 8, 9]
    assert recent == list(range(10, 30))


def test_select_turn_ranges_n_less_than_k_plus_m() -> None:
    prefix, middle, recent = select_turn_index_ranges(10, k=4, m=20)
    assert prefix == [0, 1, 2, 3]
    assert middle == []
    assert recent == list(range(0, 10))


def test_build_context_n30_includes_rag_and_excludes_middle() -> None:
    history = _history(30)
    chunk = RagChunk(doc_id="doc-a", chunk_id="c1", text="报销须在30日内提交", score=0.9)
    system_str, lc_messages = build_context(
        ["用户偏好素食"],
        "摘要：turn 5-10 已压缩",
        [chunk],
        "你是企业助手。",
        history,
        current_human="本轮改写后的问题",
        k=4,
        m=20,
    )

    assert "你是企业助手。" in system_str
    assert "User preferences" in system_str or "preferences" in system_str.lower()
    assert "- 用户偏好素食" in system_str
    assert "摘要：turn 5-10" in system_str
    assert "[doc:doc-a/chunk:c1]" in system_str
    assert "报销须在30日内提交" in system_str

    flat = " ".join(str(m.content) for m in lc_messages)
    assert "MIDDLE_T5" not in flat
    assert "MIDDLE_T10" not in flat
    assert "turn-1-human" in flat
    assert "turn-4-human" in flat
    assert "turn-11-human" in flat
    assert "turn-30-human" in flat
    assert lc_messages[-1].content == "本轮改写后的问题"

    # 4 prefix + 20 recent turns × 2 messages + 1 current human
    assert len(lc_messages) == 4 * 2 + 20 * 2 + 1


def test_build_system_prompt_uses_profile_and_filters_categorized_mem0() -> None:
    system_str = build_system_prompt(
        instructions="你是企业助手。",
        user_memories=[
            "用户叫刘日兴",
            "用户生活在哈尔滨",
            "用户偏好简洁回答",
            "用户常用差旅报销",
        ],
        summary=None,
        rag_chunks=[],
    )

    assert "## Memory profile" in system_str
    assert "profile.name: 刘日兴" in system_str
    assert "profile.city: 哈尔滨" in system_str
    assert "preference.answer_style: 简洁回答" in system_str
    assert "## User preferences" in system_str
    assert "- 用户常用差旅报销" in system_str
    assert "- 用户叫刘日兴" not in system_str
    assert "- 用户生活在哈尔滨" not in system_str
    assert "- 用户偏好简洁回答" not in system_str


def test_build_context_boundary_n_less_than_k_plus_m() -> None:
    history = _history(10, mark_middle_turns=False)
    system_str, lc_messages = build_context(
        [],
        None,
        [],
        "指令",
        history,
        current_human="当前问题",
        k=4,
        m=20,
    )
    assert system_str == "指令"
    assert len(lc_messages) == 10 * 2 + 1
    flat = " ".join(str(m.content) for m in lc_messages)
    assert "turn-1-human" in flat
    assert "turn-10-human" in flat


def test_build_context_rewrite_metadata_when_different() -> None:
    _, lc_messages = build_context(
        [],
        None,
        [],
        "",
        [],
        current_human="改写后",
        original_human="原文",
    )
    last = lc_messages[-1]
    assert isinstance(last, HumanMessage)
    assert last.content == "改写后"
    key = get_settings().CONTEXT_ORIGINAL_HUMAN_METADATA_KEY
    assert last.additional_kwargs.get(key) == "原文"


def test_build_context_uses_last_human_as_current_when_not_passed() -> None:
    history = _turn("历史", "回复")
    messages = [*history, HumanMessage(content="本轮")]
    _, lc_messages = build_context([], None, [], "", messages)
    assert len(lc_messages) == 3
    assert lc_messages[-1].content == "本轮"
    assert lc_messages[0].content == "历史"
    assert lc_messages[1].content == "回复"


def test_split_into_turns() -> None:
    turns = split_into_turns(
        [
            HumanMessage(content="h1"),
            AIMessage(content="a1"),
            HumanMessage(content="h2"),
        ]
    )
    assert len(turns) == 2
    assert len(turns[0]) == 2
    assert turns[1][0].content == "h2"


def test_build_system_prompt_skips_empty_sections() -> None:
    assert build_system_prompt(instructions="", user_memories=[], summary=None, rag_chunks=[]) == ""


def test_select_turn_ranges_rejects_negative() -> None:
    with pytest.raises(ValueError):
        select_turn_index_ranges(-1)


def test_system_prompt_applies_mem0_summary_and_rag_budgets() -> None:
    settings = Settings(  # type: ignore[arg-type]
        **_REQUIRED_ENV,
        MEMORY_PROFILE_MAX_FACTS=2,
        MEMORY_FREE_TEXT_MAX_FACTS=1,
        SUMMARY_MAX_CHARS=20,
        RAG_CHUNK_MAX_CHARS=15,
        RAG_CONTEXT_MAX_CHARS=95,
        _env_file=None,
    )
    system_str, budget = build_system_prompt_with_budget(
        instructions="指令",
        user_memories=[
            "用户叫刘日兴",
            "用户出生于1997年",
            "用户生活在哈尔滨",
            "自由事实 A",
            "自由事实 B",
        ],
        summary="s" * 80,
        rag_chunks=[
            RagChunk("doc1", "c1", "a" * 80, 0.9),
            RagChunk("doc2", "c2", "b" * 80, 0.8),
        ],
        settings=settings,
    )

    assert "profile.name: 刘日兴" in system_str
    assert "profile.birth_year: 1997" in system_str
    assert "profile.city" not in system_str
    assert "- 自由事实 A" in system_str
    assert "- 自由事实 B" not in system_str
    assert "s" * 30 not in system_str
    assert "a" * 30 not in system_str
    assert "[doc:doc1/chunk:c1]" in system_str
    assert "[doc:doc2/chunk:c2]" not in system_str
    assert budget.user_memory_count == 3
    assert budget.memory_profile_count == 2
    assert budget.memory_free_text_count == 1
    assert budget.rag_chunk_count == 1
    assert budget.budget_truncated is True


def test_build_context_caps_model_turns_and_message_chars() -> None:
    set_settings_override(
        Settings(  # type: ignore[arg-type]
            **_REQUIRED_ENV,
            MODEL_MESSAGE_MAX_TURNS=2,
            MODEL_MESSAGE_MAX_CHARS=25,
            _env_file=None,
        )
    )
    _system, lc_messages, budget = build_context_with_budget(
        user_memories=[],
        summary=None,
        rag_chunks=[],
        instructions="",
        messages=_history(5, mark_middle_turns=False),
        k=4,
        m=20,
        current_human="当前问题很长很长",
    )

    flat = " ".join(str(message.content) for message in lc_messages)
    assert "turn-1-human" not in flat
    assert "turn-5-" in flat
    assert "当前问题" in flat
    assert budget.message_chars <= 25
    assert budget.budget_truncated is True


def test_build_context_bundle_is_single_source_for_legacy_tuple() -> None:
    history = _history(6, mark_middle_turns=False)
    chunk = RagChunk(doc_id="doc-a", chunk_id="c1", text="制度正文", score=0.9)

    bundle = build_context_bundle(
        user_memories=["用户偏好简洁回答"],
        summary="历史摘要",
        rag_chunks=[chunk],
        instructions="指令",
        messages=history,
        current_human="当前问题",
        original_human="原始问题",
        k=1,
        m=2,
    )
    system_str, messages, budget = build_context_with_budget(
        user_memories=["用户偏好简洁回答"],
        summary="历史摘要",
        rag_chunks=[chunk],
        instructions="指令",
        messages=history,
        current_human="当前问题",
        original_human="原始问题",
        k=1,
        m=2,
    )

    assert bundle.system_prompt == system_str
    assert bundle.messages == messages
    assert bundle.budget == budget
    assert bundle.budget_metadata() == budget.as_metadata()
    assert bundle.sources.current_human == "当前问题"
    assert bundle.sources.original_human == "原始问题"
    assert bundle.sources.rag_chunks == (chunk,)
