"""Tests for memory.assembly — K + M + summary context assembly."""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from memory.assembly import (
    ContextAssemblyError,
    build_context,
    build_system_prompt,
    select_turn_index_ranges,
    split_into_turns,
)
from settings.config import get_settings
from rag.retriever import RagChunk


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
    assert build_system_prompt(instructions="", mem0=[], summary=None, rag_chunks=[]) == ""


def test_select_turn_ranges_rejects_negative() -> None:
    with pytest.raises(ValueError):
        select_turn_index_ranges(-1)
