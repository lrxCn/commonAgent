"""Tests for normalized memory_profile from mem0 free-text facts."""

from __future__ import annotations

from memory.profile import (
    format_memory_profile_for_system,
    normalize_memory_profile,
)


def test_normalize_memory_profile_first_batch_fields() -> None:
    normalized = normalize_memory_profile(
        [
            "用户叫刘日兴",
            "用户出生于1997年",
            "用户生活在哈尔滨",
            "用户是前端程序员",
            "我公司在天翔街188号",
            "用户偏好简洁回答",
        ]
    )

    profile = normalized.profile
    assert profile.name == "刘日兴"
    assert profile.birth_year == "1997"
    assert profile.city == "哈尔滨"
    assert profile.job == "前端程序员"
    assert profile.company_address == "天翔街188号"
    assert profile.answer_style == "简洁回答"
    assert normalized.residual_facts == []


def test_normalize_memory_profile_latest_value_wins() -> None:
    normalized = normalize_memory_profile(
        [
            "用户生活在上海",
            "用户生活在哈尔滨",
            "用户偏好详细回答",
            "用户偏好简洁回答",
        ]
    )

    assert normalized.profile.city == "哈尔滨"
    assert normalized.profile.answer_style == "简洁回答"


def test_normalize_memory_profile_keeps_uncategorized_facts() -> None:
    normalized = normalize_memory_profile(
        [
            "用户常用差旅报销",
            "用户有一只猫",
            "用户有一只猫",
        ]
    )

    assert normalized.profile.is_empty()
    assert normalized.residual_facts == ["用户常用差旅报销", "用户有一只猫"]


def test_format_memory_profile_for_system() -> None:
    normalized = normalize_memory_profile(
        [
            "用户叫刘日兴",
            "我公司在天翔街188号",
            "用户偏好简洁回答",
        ]
    )

    text = format_memory_profile_for_system(normalized.profile)

    assert "## Memory profile" in text
    assert "- profile.name: 刘日兴" in text
    assert "- company.address: 天翔街188号" in text
    assert "- preference.answer_style: 简洁回答" in text
