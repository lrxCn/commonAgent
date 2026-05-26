"""Per-turn request context for the Supervisor graph (LangGraph context_schema)."""

from __future__ import annotations

from typing import Any, TypedDict

from langgraph.runtime import Runtime

from gateway.schemas import RequestContext, ToolSpec


class GraphContextSchema(TypedDict):
    """Same shape as ``gateway.schemas.RequestContext``; passed via ``invoke(..., context=...)``."""

    user_id: str
    role_ids: list[str]
    tools: list[ToolSpec]


def graph_context_from_request(ctx: RequestContext) -> dict[str, Any]:
    """Serialize ``RequestContext`` for ``graph.invoke(..., context=...)``."""
    return ctx.model_dump()


def request_context_from_runtime(runtime: Runtime[GraphContextSchema]) -> RequestContext:
    """Resolve validated request context from the LangGraph runtime (fail fast if missing)."""
    raw = runtime.context
    if not raw:
        msg = "context is required on each invoke (user_id, role_ids, tools)"
        raise ValueError(msg)
    return RequestContext.model_validate(raw)
