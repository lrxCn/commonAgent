# Chat Turn Pipeline

回答的问题：一次 `POST /internal/chat` 从 Back 到 Agent 再到 SSE/JSON，实际经过哪些阶段。

## 主路径

1. Back 在 [context.py](/Users/liurixing/Documents/codes/ai/commonAgent/back/src/services/context.py:1) 组装 `user_id`、`role_id`、`tools[]`，再由 [forward.py](/Users/liurixing/Documents/codes/ai/commonAgent/back/src/services/forward.py:1) 转发给 Agent。
2. Agent Gateway 在 [chat.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/gateway/chat.py:1) 把请求转换成 `graph.invoke(..., context=..., configurable.thread_id=...)`。
3. 主图定义在 [build.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/graph/build.py:1)，节点导出入口在 [graph/nodes/__init__.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/graph/nodes/__init__.py:1)。

## 图阶段

按拓扑顺序：

- `inbound_guard`：入站文本护栏。
- `load_memory`：并行读取 checkpoint history、rolling summary、mem0；调用 `classify_intent()` 生成 `IntentDecision`，派生兼容 `turn_type`，执行 Policy Gate；Policy 通过时对 `fact_update` 做确定性 slot fill，写入单轮 ephemeral `memory_write_record`（fill 失败则拒绝快路径）；记录 intent/policy/fallback metadata。
- `fact_update_confirm`：仅当 `policy_fast_path_allowed=true` 且 `memory_write_record` 存在时执行；输出含字段摘要的 Commit 话术（如「已记住：姓名=张三」），跳过 LLM/RAG/Supervisor。
- `memory_query_reply`：记忆查询一等路径，只读可靠记忆证据，跳过 RAG/deepagents/mem0 写入。
- `chitchat_reply`：寒暄轻量执行器。
- `rewrite`：按 `turn_type` 决定跳过或做指代消解。
- `rag_router`：按 `turn_type`、规则或小模型决定是否走 RAG。
- `rag_retrieval`：主检索。
- `rag_subagent`：主检索为空或弱命中时二查。
- `context_assembly`：生成 `ContextBundle`。
- `supervisor`：选择执行器，必要时进入 deepagents。
- `client_actions_emit`：解析并落地客户端动作。
- `outbound_guard`：文本回复出站护栏。
- `post_turn_jobs`：异步调度 summary 和 mem0 写入；有 `memory_write_record` 时走 `store_structured_record`（`infer=False`），否则走 `extract_and_store`（`infer=True`）；`memory_query` 路径跳过 mem0 write。

## 输出路径

- 文本回合：SSE 逻辑在 [chat.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/gateway/chat.py:1)，事件契约在 [sse.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/contracts/sse.py:1)。
- `client_actions` 回合：直接返回 JSON `ChatResponse`，不做 live token streaming。

## 快速路径

- `fact_update`：必须通过 Policy Gate 且 slot fill 成功；通过后跳过 rewrite、RAG、Supervisor、outbound guard；确认话术与 `StructuredMemoryRecord` 一致。
- `memory_query`：跳过 rewrite、RAG、deepagents，并由 `post_turn_jobs` 跳过 mem0 写入。
- `chitchat`：跳过 rewrite、RAG、deepagents。
- `knowledge_query`：跳过 router 小模型，直接进入 RAG。

## 结构化记忆写入

- 写入契约：[contracts/memory_write.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/contracts/memory_write.py)
- Slot fill / 确认话术：[structured_record.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/memory/structured_record.py)
- Deterministic store：[mem0_write.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/memory/mem0_write.py) 中 `store_structured_record()`
- 双轨 post_turn：[post_turn.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/memory/post_turn.py)
- post_turn 节点：[post_turn_nodes.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/graph/nodes/post_turn_nodes.py)
- Eval seed / runner：[memory_write_seed.json](/Users/liurixing/Documents/codes/ai/commonAgent/agent/evals/memory_write_seed.json)、[run_memory_write_eval.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/scripts/run_memory_write_eval.py)

## 控制面决策点

- Intent 契约：[contracts/intent.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/contracts/intent.py:1)
- 派生 helper：[engine.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/intent/engine.py:1) 中的 `turn_type_decision_from_intent()`
- Policy Gate：[policy.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/intent/policy.py:1)
- Fallback 决策：[fallback.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/intent/fallback.py:1)
- 记忆查询执行：[query.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/memory/query.py:1)

## 实现入口

- Agent 入口：[chat.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/gateway/chat.py:1)
- 图拓扑：[build.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/graph/build.py:1)
- 节点 facade：[graph/nodes/__init__.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/graph/nodes/__init__.py:1)
- 读取与控制面节点：[memory_nodes.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/graph/nodes/memory_nodes.py:1)
- 执行器节点：[executor_nodes.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/graph/nodes/executor_nodes.py:1)

## 测试入口

- 图拓扑与 context schema：[test_graph_compile.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_graph_compile.py:1)
- 端到端 invoke 路径：[test_graph_invoke_mock.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_graph_invoke_mock.py:1)
- 路径契约：[test_path_contract.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_path_contract.py:1)
- 意图单源接入：[test_intent_shadow_graph.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_intent_shadow_graph.py:1)
- 权威对齐矩阵：[test_intent_authority_characterization.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_intent_authority_characterization.py:1)
- memory_query 路径：[test_memory_query_executor.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_memory_query_executor.py:1)
- fact_update 快路径：[test_fact_update_fast_path.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_fact_update_fast_path.py)
- 结构化记忆 eval：[test_memory_write_eval_seed.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_memory_write_eval_seed.py)、[test_memory_write_eval_runner.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_memory_write_eval_runner.py)
- SSE 行为：[test_chat_sse.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_chat_sse.py:1)
