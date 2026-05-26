"""Signal extraction for deterministic intent classification."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from gateway.schemas import ToolSpec
from graph.jump_page_catalog import has_jump_page_reference
from rag.intent import has_knowledge_intent, is_chitchat, is_user_fact_statement

_QUESTION_WORD_RE = re.compile(
    r"(?:什么|哪(?:个|些|里|儿)?|谁|怎么|怎样|如何|为什么|为何|多少|几|吗|嘛|么|呢|"
    r"what|where|who|how|why|which|when)",
    re.IGNORECASE,
)
_QUESTION_MARK_RE = re.compile(r"[?？]")
_FIRST_PERSON_RE = re.compile(r"(?:^|[，,。！？?\s])(?:我|我的|本人|俺|咱)(?:$|[^\w]|[\u4e00-\u9fff])")
_ORG_SELF_RE = re.compile(r"(?:我公司|我的公司|我们公司|咱们公司|本公司|公司|单位|我们单位)")
_ANAPHORA_RE = re.compile(
    r"(?:它|这个|那个|这些|那些|上述|刚才|前述|上面|后者|前者|继续|还有吗|同上|"
    r"that|this|it|those|them|continue|go on|same)",
    re.IGNORECASE,
)
_CONTINUATION_RE = re.compile(
    r"^(?:继续|继续说|再说|展开|详细点|还有呢|然后呢|那呢|这个呢|那个呢|它呢|"
    r"continue|go on|tell me more|more)[。.!！?？]*$",
    re.IGNORECASE,
)
_TOOL_ACTION_RE = re.compile(
    r"(?:打开|跳转|前往|进入|切换到|去|访问|open|goto|go\s+to|navigate)",
    re.IGNORECASE,
)
_NAV_TOOL_NAMES = frozenset(
    {"jumppage", "jump_page", "navigate", "navigatetopage", "openpage", "open_page"}
)
_KNOWLEDGE_TARGET_RE = re.compile(
    r"(?:制度|规定|政策|流程|步骤|办法|标准|条款|报销|手册|文档|资料|指南|规则|"
    r"要求|条件|含义|定义|材料|公司手册|知识库|查询|查一下)",
    re.IGNORECASE,
)
_COMMAND_RE = re.compile(r"^(?:请|帮我|麻烦|给我|查询|查一下|打开|跳转|前往|进入|写|生成|总结|列出)")
_SAFETY_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "prompt_injection",
        re.compile(r"(?:忽略(?:之前|以上|所有).*指令|无视.*系统|ignore.*instructions)", re.IGNORECASE),
    ),
    (
        "system_prompt_exfiltration",
        re.compile(r"(?:隐藏提示词|系统提示词|system prompt|developer message|内部指令)", re.IGNORECASE),
    ),
    (
        "sensitive_personal_data_request",
        re.compile(r"(?:私人手机号|身份证号|银行卡号|密码|验证码|private phone|password)", re.IGNORECASE),
    ),
    (
        "unauthorized_access",
        re.compile(r"(?:销售总监|老板|同事|他人|别人的).*(?:发给我|给我|查询|查)", re.IGNORECASE),
    ),
)
_FACT_ATTRIBUTE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("name", re.compile(r"(?:名字|姓名|叫)")),
    ("birthday", re.compile(r"(?:生日|出生(?:于)?|生于)")),
    ("age", re.compile(r"(?:年龄|岁)")),
    ("city", re.compile(r"(?:城市|住在|生活在|来自)")),
    ("job", re.compile(r"(?:职业|工作|职位|岗位|从事)")),
    ("company", re.compile(r"(?:公司|单位)")),
    ("address", re.compile(r"(?:地址|在哪|哪里|所在地|位于|在)")),
    ("phone", re.compile(r"(?:手机号|电话)")),
    ("email", re.compile(r"(?:邮箱|邮件)")),
    ("preference", re.compile(r"(?:喜欢|偏好|常用|不喜欢|讨厌)")),
)
_EXPLICIT_VALUE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?:是|叫|在|位于|住在|来自|出生于|生于|从事|喜欢|偏好|常用|不喜欢|讨厌)\s*([^，。！？?]+)"),
    re.compile(r"(\d{2,4}年(?:\d{1,2}月(?:\d{1,2}日)?)?)"),
    re.compile(r"([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})"),
    re.compile(r"(\d{3,4}[-\s]?\d{7,8}|1[3-9]\d{9})"),
)


@dataclass(frozen=True)
class IntentSignals:
    """Normalized text plus deterministic signals used by high-confidence rules."""

    original_text: str
    normalized_text: str
    is_empty: bool = False
    has_question_word: bool = False
    has_question_mark: bool = False
    is_question: bool = False
    is_command: bool = False
    is_first_person: bool = False
    is_org_self_reference: bool = False
    fact_attributes: tuple[str, ...] = ()
    explicit_values: tuple[str, ...] = ()
    has_explicit_value: bool = False
    legacy_user_fact_signal: bool = False
    has_knowledge_signal: bool = False
    knowledge_targets: tuple[str, ...] = ()
    is_chitchat: bool = False
    chitchat_kind: str | None = None
    has_tool_action: bool = False
    has_page_reference: bool = False
    allowed_tool_names: tuple[str, ...] = ()
    has_allowed_client_tool: bool = False
    has_anaphora: bool = False
    is_continuation: bool = False
    safety_reasons: tuple[str, ...] = ()


def normalize_text(text: str | None) -> str:
    """Normalize user text for rule matching while preserving Chinese words."""
    normalized = unicodedata.normalize("NFKC", text or "")
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def extract_signals(
    message: str | None,
    *,
    tools_context: Sequence[ToolSpec | dict[str, Any]] | None = None,
) -> IntentSignals:
    """Extract deterministic signals from a user message and per-turn tool context."""
    original = message or ""
    text = normalize_text(original)
    allowed_tools = tuple(_tool_names(tools_context))
    safety_reasons = _safety_reasons(text)
    fact_attributes = _fact_attributes(text)
    explicit_values = _explicit_values(text)
    chitchat_kind = _chitchat_kind(text)
    knowledge_targets = _knowledge_targets(text)
    has_question_word = _QUESTION_WORD_RE.search(text) is not None
    has_question_mark = _QUESTION_MARK_RE.search(text) is not None

    return IntentSignals(
        original_text=original,
        normalized_text=text,
        is_empty=not bool(text),
        has_question_word=has_question_word,
        has_question_mark=has_question_mark,
        is_question=has_question_word or has_question_mark,
        is_command=_COMMAND_RE.search(text) is not None,
        is_first_person=_FIRST_PERSON_RE.search(text) is not None or text.startswith(("我", "我的", "本人")),
        is_org_self_reference=_ORG_SELF_RE.search(text) is not None,
        fact_attributes=tuple(fact_attributes),
        explicit_values=tuple(explicit_values),
        has_explicit_value=bool(explicit_values),
        legacy_user_fact_signal=is_user_fact_statement(text),
        has_knowledge_signal=has_knowledge_intent(text),
        knowledge_targets=tuple(knowledge_targets),
        is_chitchat=is_chitchat(text),
        chitchat_kind=chitchat_kind,
        has_tool_action=_TOOL_ACTION_RE.search(text) is not None,
        has_page_reference=has_jump_page_reference(text),
        allowed_tool_names=allowed_tools,
        has_allowed_client_tool=_has_navigation_tool(allowed_tools),
        has_anaphora=_ANAPHORA_RE.search(text) is not None,
        is_continuation=_CONTINUATION_RE.match(text) is not None,
        safety_reasons=tuple(safety_reasons),
    )


def _tool_names(tools_context: Sequence[ToolSpec | dict[str, Any]] | None) -> list[str]:
    if not tools_context:
        return []
    names: list[str] = []
    for item in tools_context:
        if isinstance(item, ToolSpec):
            names.append(item.name)
        elif isinstance(item, dict) and item.get("name"):
            names.append(str(item["name"]))
    return names


def _has_navigation_tool(tool_names: Sequence[str]) -> bool:
    for name in tool_names:
        normalized = name.strip().lower().replace("-", "_")
        if normalized in _NAV_TOOL_NAMES or "jump" in normalized or "navigate" in normalized:
            return True
    return False


def _fact_attributes(text: str) -> list[str]:
    attributes: list[str] = []
    for name, pattern in _FACT_ATTRIBUTE_PATTERNS:
        if pattern.search(text):
            attributes.append(name)
    return attributes


def _explicit_values(text: str) -> list[str]:
    if not text:
        return []
    values: list[str] = []
    for pattern in _EXPLICIT_VALUE_PATTERNS:
        for match in pattern.findall(text):
            value = match.strip()
            if value and value not in values and not _looks_like_question_placeholder(value):
                values.append(value)
    return values


def _looks_like_question_placeholder(value: str) -> bool:
    return bool(_QUESTION_WORD_RE.search(value) or value in {"哪", "哪里", "在哪", "什么"})


def _knowledge_targets(text: str) -> list[str]:
    targets = _KNOWLEDGE_TARGET_RE.findall(text)
    return list(dict.fromkeys(targets))


def _chitchat_kind(text: str) -> str | None:
    if not text:
        return None
    if re.search(r"^(?:你好|您好|嗨|hi|hello|早上好|下午好|晚上好|哈喽|在吗)", text, re.IGNORECASE):
        return "greeting"
    if re.search(r"^(?:谢谢|感谢|多谢)", text):
        return "thanks"
    if is_chitchat(text):
        return "ack"
    return None


def _safety_reasons(text: str) -> list[str]:
    return [reason for reason, pattern in _SAFETY_PATTERNS if pattern.search(text)]
