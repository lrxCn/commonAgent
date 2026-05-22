# State Fields

回答的问题：`AgentState` 里每个关键字段是谁写、谁读、是否进 checkpoint。

## 持久化规则

状态定义在 [state.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/graph/state.py:1)。

- `messages`：唯一跨轮持久化字段，使用 `add_messages`。
- 其他字段：全部是 `EphemeralValue`，只在单轮 invoke 内有效。
- `user_id`、`role_id`、`tools[]`：不在 `AgentState`，而在 [context.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/graph/context.py:1) 的 `GraphContextSchema`。

## 关键字段

- `mem0_memories`、`rolling_summary`：`load_memory` 写，`context_assembly` 读。
- `turn_type`、`turn_type_reason`：`load_memory` 写，rewrite/router/executor routing 读。
- `path_metrics`：沿图逐步补充，最终用于 observability。
- `rewritten_query`：`rewrite` 写，`rag_router`、`rag_retrieval` 读。
- `rag_skipped`：`rag_router` 写，控制后续检索是否跳过。
- `rag_chunks`：`rag_retrieval` 或 `rag_subagent` 写，`context_assembly`、`rag_answer_executor` 读。
- `context_bundle`：`context_assembly` 写，`supervisor` 与执行器读。
- `system_prompt`、`context_budget`：从 `context_bundle` 派生出的兼容字段。
- `executor`、`executor_reason`：执行器路由写，observability 和测试读。
- `inbound_blocked`、`inbound_block_message`：入站护栏写，Gateway 回退输出读。
- `supervisor_draft`：文本生成阶段写，Gateway 抽取自然语言回复时读。
- `outbound_blocked`：出站护栏写。
- `client_actions`、`client_actions_error`：动作解析节点写，Gateway/历史 API 读。

## 生命周期要点

- 单轮字段如果需要跨节点传递，必须显式 carry，不能依赖下一轮 checkpoint 残留。
- `ContextBundle` 是模型上下文单一来源，避免 `system_prompt`、messages、trace metadata 分叉。

## 实现入口

- 状态定义：[state.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/graph/state.py:1)
- context schema：[context.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/graph/context.py:1)
- carry helper：[common.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/graph/nodes/common.py:1)

## 测试入口

- 生命周期约束：[test_state_lifecycle.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_state_lifecycle.py:1)
- invoke 状态读写：[test_graph_invoke_mock.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_graph_invoke_mock.py:1)
- ContextBundle 契约：[test_context_assembly.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_context_assembly.py:1)
- 契约兼容性：[test_contracts.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_contracts.py:1)
