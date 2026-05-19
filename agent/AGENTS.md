# Agents

The production Supervisor graph is defined in `src/graph/build.py` (`compile_graph` / `get_graph` for LangGraph CLI).

Supervisor LLM wiring lives in `src/graph/supervisor.py` (`create_deep_agent` from the `deepagents` package).

## Conventions

- Prefer async-native code wherever possible for performance. Tools, tests, and any new I/O should use async when the runtime supports it.
- New tools should be low-dependency and safe to run on a remote server.
- External client tools are described in the system prompt only; they are not registered as LangChain tools on the Supervisor.
- This deploys in a web server. Avoid calls to the actual file system unless using an approved sandbox backend.
