"""Executor routing before the expensive deepagents path."""

from __future__ import annotations

import re
from typing import Any, Sequence

from contracts.execution import ExecutorDecision, ExecutorType
from gateway.schemas import ClientAction, ToolSpec
from rag.retriever import RagChunk
from rag.router import is_pure_client_tool_intent


_COMPLEX_TASK_RE = re.compile(
    r"(?:规划|计划|方案|分析|比较|对比|总结|撰写|生成|设计|制定|排期|拆解|多步|复杂|"
    r"workflow|plan|analy[sz]e|compare|summari[sz]e|draft|write|design|multi-step)",
    re.IGNORECASE,
)


def _text(value: object | None) -> str:
    return "" if value is None else str(value).strip()


def _best_chunk_score(chunks: Sequence[RagChunk]) -> float:
    if not chunks:
        return 0.0
    return max(float(chunk.score) for chunk in chunks)


def _tool_names(tools: Sequence[ToolSpec]) -> list[str]:
    return [tool.name for tool in tools]


def choose_executor(
    *,
    turn_type: str,
    user_message: str,
    rewritten_query: str | None = None,
    rag_skipped: bool = False,
    rag_chunks: Sequence[RagChunk] | None = None,
    tools: Sequence[ToolSpec] | None = None,
) -> ExecutorDecision:
    """Select the cheapest executor that can satisfy this turn."""
    normalized_turn_type = _text(turn_type)
    message = _text(user_message)
    rewritten = _text(rewritten_query)
    chunks = list(rag_chunks or [])
    request_tools = list(tools or [])

    if normalized_turn_type == "fact_update":
        return ExecutorDecision(ExecutorType.TEMPLATE, "turn_type_fact_update")
    if normalized_turn_type == "chitchat":
        return ExecutorDecision(ExecutorType.SMALL_CHAT, "turn_type_chitchat")

    if (
        normalized_turn_type == "client_action"
        and is_pure_client_tool_intent(message, request_tools, rewritten_query=rewritten)
    ):
        return ExecutorDecision(ExecutorType.ACTION, "simple_client_action")

    if normalized_turn_type == "knowledge_query" and not rag_skipped and chunks:
        if _COMPLEX_TASK_RE.search(message) or _COMPLEX_TASK_RE.search(rewritten):
            return ExecutorDecision(
                ExecutorType.DEEPAGENTS,
                "complex_knowledge_task",
            )
        return ExecutorDecision(
            ExecutorType.RAG_ANSWER,
            f"rag_chunks_available_score_{_best_chunk_score(chunks):.2f}",
        )

    if request_tools and normalized_turn_type == "ambiguous":
        return ExecutorDecision(ExecutorType.DEEPAGENTS, "ambiguous_with_tools")
    if _COMPLEX_TASK_RE.search(message) or _COMPLEX_TASK_RE.search(rewritten):
        return ExecutorDecision(ExecutorType.DEEPAGENTS, "complex_task_rule")

    return ExecutorDecision(ExecutorType.DEEPAGENTS, "default_deepagents")


def build_simple_client_action(
    message: str,
    tools: Sequence[ToolSpec],
) -> ClientAction | None:
    """Build a conservative single client action for simple navigation turns."""
    text = _text(message)
    if not text or not tools:
        return None

    navigation_tool = next(
        (
            tool
            for tool in tools
            if "jump" in tool.name.lower()
            or "navigate" in tool.name.lower()
            or "open" in tool.name.lower()
        ),
        tools[0],
    )
    page = _extract_page_arg(text)
    if not page:
        return None
    return ClientAction(
        tool=navigation_tool.name,
        args={"page": page},
        requires_approval=navigation_tool.requires_approval,
    )


def _extract_page_arg(message: str) -> str:
    text = _text(message)
    match = re.search(r"(page[a-zA-Z0-9_\-]+)", text, re.IGNORECASE)
    if match:
        return match.group(1)
    match = re.search(r"页面\s*([a-zA-Z0-9_\-]+)", text, re.IGNORECASE)
    if match:
        raw = match.group(1)
        return raw if raw.lower().startswith("page") else f"page{raw}"
    match = re.search(r"/([a-zA-Z0-9_\-/]+)", text)
    if match:
        return f"/{match.group(1)}"
    return ""


def executor_trace_metadata(
    decision: ExecutorDecision,
    *,
    rag_chunks: Sequence[RagChunk] | None = None,
    tools: Sequence[ToolSpec] | None = None,
) -> dict[str, Any]:
    """Flatten executor routing decision for trace metadata."""
    chunks = list(rag_chunks or [])
    return {
        "executor": decision.executor.value,
        "executor_reason": decision.reason,
        "executor.rag_chunks_count": len(chunks),
        "executor.best_rag_score": _best_chunk_score(chunks),
        "executor.tools": _tool_names(list(tools or [])),
    }
