"""BM25 scoring for role-scoped payload candidates."""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence

from domain.rag.lexical.tokenizer import compact_text, lexical_terms
from domain.rag.models import RagCandidate

BM25_MIN_SCROLL_LIMIT = 50
BM25_SCROLL_MULTIPLIER = 8


def score_bm25(query: str, candidates: Sequence[RagCandidate], *, limit: int) -> list[RagCandidate]:
    """Score already role-filtered candidates with BM25 and exact compact-text boost."""
    query_terms = lexical_terms(query)
    if not query_terms or not candidates:
        return []

    term_counts: list[Counter[str]] = []
    lengths: list[int] = []
    df: Counter[str] = Counter()
    eligible: list[RagCandidate] = []
    for item in candidates:
        counts = Counter(lexical_terms(item.text))
        if not counts:
            continue
        eligible.append(item)
        term_counts.append(counts)
        length = sum(counts.values())
        lengths.append(length)
        df.update(counts.keys())

    if not eligible:
        return []

    query_counts = Counter(query_terms)
    total_docs = len(eligible)
    avg_len = max(1.0, sum(lengths) / total_docs)
    compact_query = compact_text(query)
    k1 = 1.5
    b = 0.75

    scored: list[RagCandidate] = []
    for item, counts, doc_len in zip(eligible, term_counts, lengths, strict=True):
        score = 0.0
        for term, query_count in query_counts.items():
            term_freq = counts.get(term, 0)
            if term_freq <= 0:
                continue
            doc_freq = max(1, df.get(term, 0))
            idf = math.log(1.0 + (total_docs - doc_freq + 0.5) / (doc_freq + 0.5))
            denom = term_freq + k1 * (1.0 - b + b * (doc_len / avg_len))
            score += query_count * idf * ((term_freq * (k1 + 1.0)) / denom)
        if compact_query and compact_query in compact_text(item.text):
            score += 2.0
        if score > 0.0:
            scored.append(item.with_score(score, channel="bm25"))

    return sorted(scored, key=lambda item: item.score, reverse=True)[:limit]
