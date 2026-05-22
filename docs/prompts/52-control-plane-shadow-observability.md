# 52 - 控制面 Phase 3：Intent Engine 影子运行与观测接入

## 建议执行模型

- 模型：GPT-5.5
- Reasoning：high
- 原因：本任务把新控制面接入主图但不改变执行路径，需要保证 shadow 结果可观测、可对比、不会影响线上行为。

## 依赖

51

## 背景

控制面 PRD 要求渐进迁移。新 `IntentDecision` 不能一上来替换旧 `turn_type`，应先影子运行，记录旧分类与新 route 的差异，让 trace 和 eval 先暴露分歧。

## 目标

- 在 graph 的 `load_memory` / classification 阶段旁路运行 `classify_intent()`。
- state 中新增单轮 intent 影子字段。
- LangSmith metadata / domain events 记录新旧分类、置信度、冲突和 fallback 候选。
- 不改变当前执行路径，不改变用户可见行为。

## 范围

| 模块 | 变更 |
|------|------|
| `agent/src/graph/state.py` | 新增单轮 ephemeral intent shadow 字段，如 `intent_decision`、`intent_conflict` |
| `agent/src/graph/nodes/memory_nodes.py` 或新增 `intent_nodes.py` | 在现有 turn type 分类旁运行 `classify_intent()` |
| `agent/src/contracts/events.py` | 新增 `IntentClassified` / `IntentConflictDetected` 事件 |
| `agent/src/infrastructure/langsmith/metadata_mapper.py` | 映射 intent metadata |
| `agent/src/observability/` | 如需要，补事件 collector helper |
| `agent/tests/test_intent_shadow_graph.py` | 断言 shadow 运行不改变旧路径 |
| `agent/tests/test_tracing.py` | 断言 metadata 包含 intent 字段 |
| `agent/tests/test_path_contract.py` | 断言旧 path contract 不漂移 |
| `docs/progress.md` | 本任务状态 |

## 观测字段

trace metadata 至少包含：

```text
intent.speech_act
intent.domain
intent.operation
intent.route
intent.confidence
intent.risk
intent.reasons
intent.needs_clarification
intent.legacy_turn_type
intent.legacy_turn_type_reason
intent.conflict
intent.conflict_reason
```

## 行为约束

- 当前 graph 仍按旧 `turn_type` 走路径。
- shadow intent 不允许触发 fast path、RAG、memory write 或 client_actions。
- 如果 shadow classifier 失败，不影响本轮旧路径，只记录 `intent.shadow_error`。
- `path_contract` 仍按当前行为验收。

## 非范围

- 不让 Policy Gate 接管 fast path。
- 不新增 `memory_query` 路由。
- 不改变 executor router。
- 不改变 SSE 输出。
- 不更新 README 当前运行契约。

## 测试方案

```bash
cd agent
uv run pytest tests/test_intent_shadow_graph.py tests/test_graph_invoke_mock.py tests/test_path_contract.py -v
uv run pytest tests/test_tracing.py tests/test_contracts.py -v
uv run ruff check src tests
```

## 完成标准

- [ ] 新 `IntentDecision` 在主图中影子运行。
- [ ] trace 能看到旧 `turn_type` 与新 `intent.route`。
- [ ] shadow 失败不影响本轮响应。
- [ ] 所有旧路径行为测试保持不变。
- [ ] `docs/progress.md` 同步。

## 进度更新

`docs/progress.md` **52** → 实现完成后改为 `✅`。
