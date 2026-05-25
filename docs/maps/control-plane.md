# Control Plane

回答的问题：Intent、Policy Gate、memory_query、Fallback 和 Feedback/Eval 当前如何落地，哪些入口是运行时事实。

## 运行时事实

- `load_memory` 节点在读取 checkpoint、summary、mem0 后，调用 `classify_intent()` 生成 `IntentDecision`，再通过 `turn_type_decision_from_intent()` 派生兼容 `turn_type` / `turn_type_reason`。
- 当前 graph 热路径使用确定性 `classify_intent()`：normalize -> signals -> rules，不调用 LLM。
- `IntentDecision` 是唯一意图权威；`turn_type` 是派生兼容字段，与 `intent_decision.turn_type` 同源。
- `graph.turn_type.classify_turn_type()` 保留为兼容 adapter，内部委托同一 authority，不再独立分类。
- `intent_conflict` / `intent_conflict_reason` 保留兼容字段，常态为 `false` / 空；分类失败时写 `intent_shadow_error` 并保守回退 `general_chat`。
- Policy Gate 当前只准入 `fact_update` 快速路径，不是通用鉴权系统。
- `memory_query` 已是一等路径，直接进入 `memory_query_reply`，不走 RAG、deepagents 或 mem0 write。
- Fallback Manager 不执行恢复动作本身，只产出标准 `FallbackDecision`，由节点写入 path metrics 和事件。

## 核心契约

- Intent 契约：[contracts/intent.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/contracts/intent.py:1)
- 派生 helper：[engine.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/intent/engine.py:1) 中的 `turn_type_decision_from_intent()`
- Fallback 契约：[contracts/fallback.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/contracts/fallback.py:1)
- LLM 用途：[contracts/llm.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/contracts/llm.py:1)
- Path metrics：[path_contract.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/observability/path_contract.py:1)

## Intent Engine

- Signals：[signals.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/intent/signals.py:1)
- 确定性规则：[rules.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/intent/rules.py:1)
- 纯入口与派生：[engine.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/intent/engine.py:1)
- 兼容 adapter：[turn_type.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/graph/turn_type.py:1)
- Structured classifier：[classifier.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/intent/classifier.py:1)

`INTENT_CLASSIFIER` 已接入 LLM Gateway policy，包含 schema 校验、repair 和冲突 fallback；当前主图没有在热路径调用它。

## Policy Gate

[policy.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/intent/policy.py:1) 的 `decide_fast_path_policy()` 当前检查：

- `speech_act=statement`
- `operation=memory_write`
- `route=fact_update`
- `confidence >= 0.9`
- `risk=low`
- 不是疑问句
- 有显式事实属性和值

通过后才允许 `fact_update_confirm`。拒绝后会记录 `policy_denied_reason`，旧事实路径不会模板确认，也不会触发 mem0 写入。

## memory_query

- 路由分支：[routing_nodes.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/graph/nodes/routing_nodes.py:1)
- 执行节点：[executor_nodes.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/graph/nodes/executor_nodes.py:1)
- 证据回答：[query.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/memory/query.py:1)
- post_turn 跳过写入：[post_turn_nodes.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/graph/nodes/post_turn_nodes.py:1)

回答只基于 memory profile、mem0 文本或当前 thread 里的可靠用户事实；没有证据时返回诚实缺失回复，并记录 memory fallback。

## Fallback

[fallback.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/intent/fallback.py:1) 统一覆盖：

- intent low confidence / classify error
- policy denied
- memory missing
- RAG empty / weak hit
- tool unavailable / not allowed / schema invalid
- LLM timeout / provider error
- structured output invalid
- output guard
- checkpoint failure

节点通过 [record_fallback_decision()](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/observability/path_contract.py:103) 写入 `fallback.*` metadata，并 emit `FALLBACK_TRIGGERED`。

## Feedback 与 Eval

- Feedback helper：[feedback.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/intent/feedback.py:1)
- 控制面 seed：[intent_seed.json](/Users/liurixing/Documents/codes/ai/commonAgent/agent/evals/intent_seed.json)
- Eval 说明：[agent/evals/README.md](/Users/liurixing/Documents/codes/ai/commonAgent/agent/evals/README.md:1)
- 本地 runner：[run_intent_eval.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/scripts/run_intent_eval.py:1)
- LangSmith dry-run 同步：[sync_langsmith_dataset.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/scripts/sync_langsmith_dataset.py:1)

Feedback 样本需要人工确认后进入 seed；第一人称疑问误判为事实写入的反例必须保留。

## 测试入口

- 派生契约：[test_intent_authority_contract.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_intent_authority_contract.py:1)
- 单源对齐矩阵：[test_intent_authority_characterization.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_intent_authority_characterization.py:1)
- 兼容 adapter：[test_turn_type.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_turn_type.py:1)
- Intent 契约：[test_intent_contracts.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_intent_contracts.py:1)
- Signals / rules：[test_intent_signals.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_intent_signals.py:1)、[test_intent_rules.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_intent_rules.py:1)
- Structured classifier：[test_intent_classifier.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_intent_classifier.py:1)
- Graph 单源接入：[test_intent_shadow_graph.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_intent_shadow_graph.py:1)
- Policy Gate：[test_policy_gate.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_policy_gate.py:1)
- memory_query：[test_memory_query_executor.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_memory_query_executor.py:1)
- Fallback：[test_fallback_manager.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_fallback_manager.py:1)
- Feedback / eval：[test_intent_feedback.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_intent_feedback.py:1)、[test_intent_eval_seed.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_intent_eval_seed.py:1)、[test_intent_eval_runner.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_intent_eval_runner.py:1)
