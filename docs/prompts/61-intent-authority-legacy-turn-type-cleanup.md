# 61 - 意图权威收敛 Phase 3：旧 turn_type 分类器降级与清理

## 建议执行模型

- 模型：GPT-5.5
- Reasoning：medium
- 原因：本任务以兼容清理为主，但会影响旧导入路径和测试命名，需要谨慎保留 facade，避免破坏外部调用。

## 新窗口执行规则

1. 先读根目录 `AGENTS.md`、`README.md`、`docs/progress.md` 和本任务卡；如修改 `agent/`，同时读 `agent/AGENTS.md`。
2. 核对 `docs/progress.md` 中本任务依赖是否完成；未完成则停止。
3. 对比当前模型和 reasoning 与本节建议；如果不一致或未知，先告诉用户建议配置并等待确认，除非用户明确要求继续。
4. 只实现本任务范围，不顺手做相邻任务。
5. 按本任务测试计划验证。
6. 测试通过后更新 `docs/progress.md`。

## 依赖

60

## 背景

主图切到 `IntentDecision` 单源后，旧 `graph.turn_type.classify_turn_type()` 仍可能被测试或外部导入使用。它应降级为兼容 adapter，而不是继续拥有独立规则。

## 目标

- `graph.turn_type.classify_turn_type()` 保留导出，但内部委托控制面分类与派生 helper。
- 移除 `graph.turn_type` 对 `rag.intent.is_user_fact_statement()`、`has_knowledge_intent()`、`is_chitchat()` 等全局分类启发式的直接依赖。
- 更新旧测试名称和断言，使其表达“兼容 adapter”而不是“第二套权威规则”。
- 保留 `rag.intent` 局部 helper 给 rewrite/router 使用，不做误删。

## 范围

| 模块 | 变更 |
|------|------|
| `agent/src/graph/turn_type.py` | 降级为兼容 adapter，委托 intent authority |
| `agent/tests/test_turn_type.py` | 改为 adapter 兼容测试，去掉旧误判期望 |
| `agent/tests/test_rewrite.py` / `test_rag_router.py` | 如断言依赖旧 reason，更新为派生 reason |
| `agent/tests/test_intent_rules.py` | 确认真实规则测试集中在 intent 层 |
| `docs/progress.md` | 本任务完成后更新状态和日志 |

## 实施步骤

1. 搜索所有 `classify_turn_type` 导入和调用点。
2. 将 `graph.turn_type.classify_turn_type()` 改为调用控制面 authority，并返回兼容 `TurnTypeDecision`。
3. 保留 `_is_ambiguous_reference` 等仅当仍被 adapter 需要；无用则删除。
4. 更新测试断言，明确旧第一人称疑问不再期望 `fact_update`。
5. 确认 `rag.intent.py` 没有被误删，rewrite/router 局部规则仍可用。

## 验证方案

```bash
cd agent
uv run pytest tests/test_turn_type.py tests/test_intent_rules.py tests/test_intent_authority_contract.py -v
uv run pytest tests/test_rewrite.py tests/test_rag_router.py tests/test_graph_invoke_mock.py -v
uv run python scripts/run_intent_eval.py --seed evals/intent_seed.json --json
uv run ruff check src tests
```

## 非范围

- 不删除 `TurnType` enum。
- 不删除 `IntentDecision.turn_type` property。
- 不删除 `rag.intent` 局部 helper。
- 不更新 README/maps；最终文档在任务 62。

## 完成标准

- [ ] 旧 `classify_turn_type()` 不再独立分类。
- [ ] 所有 `turn_type` 兼容测试指向同一个 intent authority。
- [ ] rewrite/router 仍通过局部测试。
- [ ] 验证命令通过。
- [ ] `docs/progress.md` 更新。

## 进度更新

`docs/progress.md` **61** → 实现完成后改为 `✅`。
