# 13 - Supervisor 主图

## 依赖

03, 06, 09, 10, 11, 12

## 目标

用 **deepagents / LangGraph** 组装主图：入站护栏 → 并行 mem0+history → rewrite → RAG 路由+检索 → 组装 → **Supervisor** 生成回复。

## 范围

- `agent/src/graph/state.py`：AgentState（含 rewritten_query, rag_chunks, rag_skipped, context 等）
- `agent/src/graph/nodes.py`：各节点
- `agent/src/graph/build.py`：`compile_graph(checkpointer)`
- Supervisor 使用 deepagents 内置能力（规划等按需启用）

## 非范围

- RagSubAgent（14）
- client_actions 专用输出（16）
- SSE（18）

## 实现要点

- `context` 每轮从 invoke input 注入，**不** persist 到 checkpoint 作为权威权限源
- mem0 与 checkpoint **并行**（asyncio.gather 或 LangGraph Send）
- 内置工具与外部 tools 列表分离

## 测试方案

```bash
cd agent
uv run pytest tests/test_graph_compile.py -v
uv run pytest tests/test_graph_invoke_mock.py -v
```

mock LLM：一轮 invoke 后 state 含 ai 消息；rag_skipped 路径不调用 retriever（mock 断言 call_count）。

## 完成标准

- `langgraph dev` 或等价可加载图
- 端到端 mock 测试通过

## 进度更新

`docs/progress.md` **13** → `✅`
