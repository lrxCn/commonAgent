# Chat Turn Pipeline

回答的问题：一次 `POST /internal/chat` 从 Back 到 Agent 再到 SSE/JSON，实际经过哪些阶段。

## 主路径

1. Back 在 [context.py](/Users/liurixing/Documents/codes/ai/commonAgent/back/src/services/context.py:1) 组装 `user_id`、`role_id`、`tools[]`，再由 [forward.py](/Users/liurixing/Documents/codes/ai/commonAgent/back/src/services/forward.py:1) 转发给 Agent。
2. Agent Gateway 在 [chat.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/gateway/chat.py:1) 把请求转换成 `graph.invoke(..., context=..., configurable.thread_id=...)`。
3. 主图定义在 [build.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/graph/build.py:1)，节点导出入口在 [graph/nodes/__init__.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/graph/nodes/__init__.py:1)。

## 图阶段

按拓扑顺序：

- `inbound_guard`：入站文本护栏。
- `load_memory`：并行读取 checkpoint history、rolling summary、mem0，并确定 `turn_type`。
- `fact_update_confirm`：事实更新快速路径模板确认。
- `chitchat_reply`：寒暄轻量执行器。
- `rewrite`：按 `turn_type` 决定跳过或做指代消解。
- `rag_router`：按 `turn_type`、规则或小模型决定是否走 RAG。
- `rag_retrieval`：主检索。
- `rag_subagent`：主检索为空或弱命中时二查。
- `context_assembly`：生成 `ContextBundle`。
- `supervisor`：选择执行器，必要时进入 deepagents。
- `client_actions_emit`：解析并落地客户端动作。
- `outbound_guard`：文本回复出站护栏。
- `post_turn_jobs`：异步调度 summary 和 mem0 写入。

## 输出路径

- 文本回合：SSE 逻辑在 [chat.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/gateway/chat.py:1)，事件契约在 [sse.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/contracts/sse.py:1)。
- `client_actions` 回合：直接返回 JSON `ChatResponse`，不做 live token streaming。

## 快速路径

- `fact_update`：跳过 rewrite、RAG、Supervisor、outbound guard。
- `chitchat`：跳过 rewrite、RAG、deepagents。
- `knowledge_query`：跳过 router 小模型，直接进入 RAG。

## 实现入口

- Agent 入口：[chat.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/gateway/chat.py:1)
- 图拓扑：[build.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/graph/build.py:1)
- 节点 facade：[graph/nodes/__init__.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/graph/nodes/__init__.py:1)

## 测试入口

- 图拓扑与 context schema：[test_graph_compile.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_graph_compile.py:1)
- 端到端 invoke 路径：[test_graph_invoke_mock.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_graph_invoke_mock.py:1)
- 路径契约：[test_path_contract.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_path_contract.py:1)
- SSE 行为：[test_chat_sse.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_chat_sse.py:1)
