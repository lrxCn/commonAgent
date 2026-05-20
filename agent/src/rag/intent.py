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
