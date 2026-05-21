"""Shared intent heuristics for rewrite skip and RAG routing (no circular imports)."""

from __future__ import annotations

import re

# --- Rule patterns (chitchat / knowledge) ---

_CHITCHAT_RE = re.compile(
    r"^(?:你好|您好|嗨|hi|hello|早上好|下午好|晚上好|谢谢|感谢|多谢|再见|拜拜|"
    r"在吗|哈喽|ok|okay|好的|嗯|嗯嗯|收到)[\s!！。.?？~，,]*$",
    re.IGNORECASE,
)

_KNOWLEDGE_RE = re.compile(
    r"(?:是什么|什么是|是啥|有哪些|有没有|如何|怎么|怎样|为什么|为何|多少|哪(?:个|些|里)|"
    r"介绍|说明|解释|查询|查一下|了解|制度|规定|政策|流程|步骤|办法|标准|条款|报销|手册|文档|"
    r"资料|指南|规则|要求|条件|含义|定义|\?|？)",
    re.IGNORECASE,
)

_QUESTION_RE = re.compile(r"(?:吗|嘛|么|呢|？|\?)\s*$")

_USER_FACT_RE = re.compile(
    r"^(?:我公司|我的公司|我们公司|公司|单位|我们|我的|我|本人|用户|咱|俺)?"
    r"(?:的)?"
    r"(?:出生|生日|年龄|姓名|名字|职业|工作|职位|岗位|公司|单位|城市|地址|所在地|生活|"
    r"手机号|电话|邮箱|微信|偏好|喜欢|常用|不喜欢|讨厌|是|叫|在|位于|住在|来自|出生于|生于|从事)",
    re.IGNORECASE,
)


def _text(value: str | None) -> str:
    return (value or "").strip()


def _combined_query(message: str, rewritten_query: str | None) -> str:
    original = _text(message)
    rewritten = _text(rewritten_query)
    if rewritten and rewritten != original:
        return f"{original}\n{rewritten}"
    return original or rewritten


def is_chitchat(message: str, rewritten_query: str | None = None) -> bool:
    """Greeting/thanks-only turns that should skip RAG (and often rewrite LLM)."""
    for text in (_text(message), _text(rewritten_query)):
        if not text:
            continue
        if _CHITCHAT_RE.match(text):
            return True
        if len(text) <= 4 and text in {"好", "行", "嗯"}:
            return True
    return False


def has_knowledge_intent(message: str, rewritten_query: str | None = None) -> bool:
    """Detect FAQ / policy / how-to style questions."""
    combined = _combined_query(message, rewritten_query)
    if not combined:
        return False
    return _KNOWLEDGE_RE.search(combined) is not None


def is_user_fact_statement(message: str, rewritten_query: str | None = None) -> bool:
    """Detect first-party facts that should update memory, not query KB."""
    for text in (_text(message), _text(rewritten_query)):
        if not text:
            continue
        if _QUESTION_RE.search(text) or has_knowledge_intent(text):
            continue
        if _USER_FACT_RE.search(text):
            return True
    return False
