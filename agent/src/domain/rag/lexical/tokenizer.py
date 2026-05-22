"""Low-dependency tokenizer for lexical RAG fallback."""

from __future__ import annotations

import re

_LEXICAL_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]+")


def lexical_terms(text: str) -> list[str]:
    """Tokenize English words and Chinese character n-grams."""
    normalized = text.strip().lower()
    if not normalized:
        return []

    terms: list[str] = []
    for match in _LEXICAL_TOKEN_RE.finditer(normalized):
        token = match.group(0)
        if not token:
            continue
        if all("\u4e00" <= ch <= "\u9fff" for ch in token):
            chars = list(token)
            terms.extend(chars)
            terms.extend("".join(chars[i : i + 2]) for i in range(len(chars) - 1))
            terms.extend("".join(chars[i : i + 3]) for i in range(len(chars) - 2))
            if len(token) <= 12:
                terms.append(token)
            continue
        terms.append(token)
    return terms


def compact_text(text: str) -> str:
    return re.sub(r"\s+", "", text.strip().lower())
