# Agents

Read the repository root `AGENTS.md` first, then `README.md`, before changing this service. The root files are the cross-tool behavior and architecture sources of truth.

The production Supervisor graph is defined in `src/graph/build.py` (`compile_graph` / `get_graph` for LangGraph CLI).

Supervisor LLM wiring lives in `src/graph/supervisor.py` (`create_deep_agent` from the `deepagents` package).

## Invoking the graph

Each chat turn must pass **request context** and **thread id** separately from checkpoint state:

```python
from langchain_core.messages import HumanMessage
from graph.build import compile_graph
from graph.context import graph_context_from_request
from gateway.schemas import RequestContext

graph = compile_graph()
graph.invoke(
    {"messages": [HumanMessage(content=user_message)]},
    context=graph_context_from_request(
        RequestContext(user_id="...", role_id="...", tools=[...])
    ),
    config={"configurable": {"thread_id": thread_id}},
)
```

- `context=` — per-turn `user_id`, `role_id`, `tools[]` (`GraphContextSchema`); **not** stored in `AgentState` or used as checkpoint authority.
- `config.configurable.thread_id` — checkpointer session key (conversation id).
- Do **not** pass `context` or `user_message` inside the state dict; derive the user text from the last `HumanMessage` in `messages`.

Single-turn pipeline fields (`rewritten_query`, `rag_chunks`, `mem0_*`, etc.) use `EphemeralValue` in `AgentState` and must not be relied on across invokes.

## Conventions

- Prefer async-native code wherever possible for performance. Tools, tests, and any new I/O should use async when the runtime supports it.
- New tools should be low-dependency and safe to run on a remote server.
- External client tools are described in the system prompt only; they are not registered as LangChain tools on the Supervisor.
- This deploys in a web server. Avoid calls to the actual file system unless using an approved sandbox backend.
