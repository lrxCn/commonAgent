"""Rerank client adapter for OpenAI-compatible rerank endpoints."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

from settings.config import Settings, get_settings

logger = logging.getLogger(__name__)


def default_rerank(query: str, documents: list[str], *, settings: Settings | None = None) -> list[float]:
    """Rerank via SiliconFlow / OpenAI-compatible ``/rerank`` endpoint."""
    if not documents:
        return []

    cfg = settings or get_settings()
    payload = {
        "model": cfg.RERANK_MODEL,
        "query": query,
        "documents": documents,
        "top_n": len(documents),
    }
    url = f"{cfg.OPENAI_BASE_URL.rstrip('/')}/rerank"
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {cfg.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
        logger.debug("rerank API failed; using retrieval order", exc_info=True)
        return [float(len(documents) - i) for i in range(len(documents))]

    results = body.get("results") if isinstance(body, dict) else None
    if not isinstance(results, list):
        return [float(len(documents) - i) for i in range(len(documents))]

    scores = [0.0] * len(documents)
    for item in results:
        if not isinstance(item, dict):
            continue
        index = item.get("index")
        score = item.get("relevance_score", item.get("score"))
        if isinstance(index, int) and 0 <= index < len(documents) and score is not None:
            scores[index] = float(score)
    if all(s == 0.0 for s in scores):
        return [float(len(documents) - i) for i in range(len(documents))]
    return scores
