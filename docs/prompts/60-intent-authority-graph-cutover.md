# 60 - 意图权威收敛 Phase 2：Graph 切换到 IntentDecision 单源

## 建议执行模型

- 模型：GPT-5.5
- Reasoning：high
- 原因：本任务正式改变主图 `turn_type` 来源，影响 rewrite、RAG、executor、Policy Gate、path metrics 和 LangSmith metadata，必须用 characterization 与 eval 护住行为。

## 新窗口执行规则

1. 先读根目录 `AGENTS.md`、`README.md`、`docs/progress.md` 和本任务卡；如修改 `agent/`，同时读 `agent/AGENTS.md`。
2. 核对 `docs/progress.md` 中本任务依赖是否完成；未完成则停止。
3. 对比当前模型和 reasoning 与本节建议；如果不一致或未知，先告诉用户建议配置并等待确认，除非用户明确要求继续。
4. 只实现本任务范围，不顺手做相邻任务。
5. 按本任务测试计划验证。
6. 测试通过后更新 `docs/progress.md`。

## 依赖

59

## 背景

目前 `load_memory_node()` 会先调用旧 `classify_turn_type()` 写入 `state.turn_type`，再调用 `classify_intent()` 写入 `state.intent_decision`。本任务把主图切到单源：先产出 `IntentDecision`，再派生兼容 `turn_type`。

## 目标

- `load_memory_node()` 每轮只调用一个权威意图分类入口。
- `state.turn_type` 与 `state.intent_decision.turn_type` 同源。
- 第一人称疑问、事实写入、知识查询、client action、chitchat、ambiguous 的路径符合任务 58 的目标矩阵。
- 保留必要的 trace/path metadata，但不再把旧分类与新分类的分歧当作常态。

## 范围

| 模块 | 变更 |
|------|------|
| `agent/src/graph/nodes/memory_nodes.py` | 调整 `load_memory_node()` 分类顺序和写入来源 |
| `agent/src/graph/state.py` | 如字段语义需要说明，更新注释；不随意删除兼容字段 |
| `agent/src/observability/path_contract.py` | 确保 path metrics 读取派生后的 `turn_type` |
| `agent/src/infrastructure/langsmith/metadata_mapper.py` | 如 metadata 字段含义变化，更新映射或测试 |
| `agent/tests/test_intent_shadow_graph.py` / 新测试 | 覆盖单源写入与无双重分类 |
| `agent/tests/test_path_contract.py` | 覆盖派生 `turn_type` 后路径契约 |
| `docs/progress.md` | 本任务完成后更新状态和日志 |

## 实施步骤

1. 基于任务 59 的派生 helper 修改 `load_memory_node()`。
2. 保证 `IntentDecision`、`turn_type`、`turn_type_reason`、Policy Gate、fallback metadata 使用同一份用户消息和 tools context。
3. 更新原 shadow/conflict 测试：分歧观测不再是常态；如保留 `intent_conflict`，应为 false/空或仅记录异常。
4. 跑 characterization、intent eval 和路径测试，确认目标矩阵通过。

## 验证方案

```bash
cd agent
uv run pytest tests/test_intent_authority_characterization.py tests/test_intent_authority_contract.py -v
uv run pytest tests/test_intent_shadow_graph.py tests/test_policy_gate.py tests/test_memory_query_executor.py tests/test_path_contract.py -v
uv run pytest tests/test_rewrite.py tests/test_rag_router.py tests/test_graph_invoke_mock.py -v
uv run python scripts/run_intent_eval.py --seed evals/intent_seed.json --json
uv run ruff check src tests
```

## 非范围

- 不删除旧 `graph.turn_type.classify_turn_type()`；清理在任务 61。
- 不改变 `INTENT_CLASSIFIER` hot path 策略。
- 不重写 RAG 检索或 memory query executor。
- 不更新 README 当前运行契约；最终文档在任务 62。

## 完成标准

- [ ] `load_memory_node()` 不再并行调用旧 `classify_turn_type()` 和新 `classify_intent()`。
- [ ] `state.turn_type` 从 `IntentDecision` 派生。
- [ ] 关键路径测试和 intent eval 通过。
- [ ] 第一人称疑问不可能因旧 `turn_type` 来源进入事实写入路径。
- [ ] `docs/progress.md` 更新。

## 进度更新

`docs/progress.md` **60** → 实现完成后改为 `✅`。
