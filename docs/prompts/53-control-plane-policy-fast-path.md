# 53 - 控制面 Phase 4：Policy Gate 接管 fact_update fast path

## 建议执行模型

- 模型：GPT-5.5
- Reasoning：high
- 原因：本任务正式改变事实写入快速路径的准入规则，必须防止旧 `turn_type` 误判继续触发模板确认、mem0 写入或下游跳过。

## 依赖

52

## 背景

当前 `fact_update` fast path 权力过大：一旦旧规则误判，就会跳过 rewrite、RAG、Supervisor，并调度 mem0 写入。控制面 PRD 要求 fast path 必须由 Policy Gate 准入，而不是由事实正则或旧 `turn_type` 直接决定。

## 目标

- 新增 Policy Gate，负责判断 `IntentDecision` 是否允许进入 fast path。
- `fact_update` 快速路径只接受高置信、低风险、明确属性和值、无疑问信号的 `memory_write`。
- 第一人称疑问句不再可能触发 fact_update 模板确认或 mem0 写入。
- `memory_query` executor 未完成前，相关输入可临时降级到保守 general/deepagents 路径，但不得进入 fact_update。

## 范围

| 模块 | 变更 |
|------|------|
| `agent/src/intent/policy.py` | `PolicyDecision`、fast path 准入、deny reason |
| `agent/src/graph/state.py` | 新增 policy 单轮字段，如 `policy_fast_path_allowed`、`policy_denied_reason` |
| `agent/src/graph/nodes/routing_nodes.py` | `after_memory_route` 改为消费 Policy Gate 结果，而不是裸 `turn_type=fact_update` |
| `agent/src/graph/nodes/executor_nodes.py` | fact_update 模板只在 policy allow 时执行 |
| `agent/src/memory/post_turn.py` | mem0 写入调度不得因旧误判触发 |
| `agent/src/rag/rewrite.py` / `agent/src/rag/router.py` | 避免被 denied fact_update 的旧 `turn_type` 继续跳过正常路径 |
| `agent/tests/test_policy_gate.py` | 覆盖准入与拒绝矩阵 |
| `agent/tests/test_fact_update_fast_path.py` | 更新 fast path 断言 |
| `agent/tests/test_turn_type.py` / `test_intent_rules.py` | 补第一人称疑问反例 |
| `agent/tests/test_post_turn_graph.py` | 断言 denied fact_update 不调度 mem0 write |
| `docs/progress.md` | 本任务状态 |

## fast path 准入条件

必须同时满足：

```text
speech_act == statement
operation == memory_write
confidence >= 0.9
risk == low
has_explicit_attribute == true
has_explicit_value == true
no_question_signal == true
```

## 必须拒绝的输入

```text
我是谁
我叫什么
我的名字是什么
我公司在哪
我喜欢什么
我是做什么的
你知道我是谁吗
```

拒绝后要求：

- 不进入 `fact_update_confirm`。
- 不返回“已记住”模板。
- 不调度 mem0 写入。
- trace 记录 `policy.fast_path_allowed=false` 和 deny reason。

## 非范围

- 不实现正式 `memory_query` executor；该工作在任务 54。
- 不引入 HITL；该工作在任务 56。
- 不改变 RAG 质量策略。
- 不更新 README 当前运行契约。

## 测试方案

```bash
cd agent
uv run pytest tests/test_policy_gate.py tests/test_fact_update_fast_path.py tests/test_post_turn_graph.py -v
uv run pytest tests/test_graph_invoke_mock.py tests/test_path_contract.py tests/test_rewrite.py tests/test_rag_router.py -v
uv run ruff check src tests
```

## 完成标准

- [ ] fact_update fast path 必须由 Policy Gate 准入。
- [ ] 第一人称疑问句不会触发模板确认或 mem0 写入。
- [ ] 事实写入正例仍能 0 LLM、0 RAG 快速确认。
- [ ] denied fast path 有 trace metadata 和 path contract 记录。
- [ ] 本任务行为变化有专门测试覆盖。
- [ ] `docs/progress.md` 同步。

## 进度更新

`docs/progress.md` **53** → 实现完成后改为 `✅`。
