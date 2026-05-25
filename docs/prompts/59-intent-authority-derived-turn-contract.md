# 59 - 意图权威收敛 Phase 1：单一权威派生契约

## 建议执行模型

- 模型：GPT-5.5
- Reasoning：high
- 原因：本任务引入新的兼容派生契约，后续 graph 切换会依赖它；需要保持类型、trace reason、旧导入路径和测试兼容。

## 新窗口执行规则

1. 先读根目录 `AGENTS.md`、`README.md`、`docs/progress.md` 和本任务卡。
2. 核对 `docs/progress.md` 中本任务依赖是否完成；未完成则停止。
3. 对比当前模型和 reasoning 与本节建议；如果不一致或未知，先告诉用户建议配置并等待确认，除非用户明确要求继续。
4. 只实现本任务范围，不顺手做相邻任务。
5. 按本任务测试计划验证。
6. 测试通过后更新 `docs/progress.md`。

## 依赖

58

## 背景

切换前需要先有稳定契约：`IntentDecision` 是唯一语义来源，`TurnTypeDecision` 只是从 `IntentDecision.route` 和 reason 派生的兼容对象。

## 目标

- 新增或明确一个从 `IntentDecision` 派生 `TurnTypeDecision` 的 helper。
- 保证派生逻辑只依赖 `IntentDecision.turn_type` / `turn_type_reason`。
- 为后续 graph 切换提供单元测试，不改变主图运行路径。

## 范围

| 模块 | 变更 |
|------|------|
| `agent/src/intent/engine.py` 或新建小模块 | 增加 `classify_turn_from_intent()` / `turn_type_decision_from_intent()` 等派生 helper |
| `agent/src/contracts/intent.py` | 如有必要补充注释，不改变既有字段语义 |
| `agent/src/graph/turn_type.py` | 暂不切换运行实现；可只添加 deprecation 注释或 adapter 准备 |
| `agent/tests/test_intent_authority_contract.py` | 覆盖派生契约与 reason code |
| `docs/progress.md` | 本任务完成后更新状态和日志 |

## 契约要求

- `TurnTypeDecision.turn_type == intent_decision.turn_type`。
- `TurnTypeDecision.reason == intent_decision.turn_type_reason`。
- helper 不调用 LLM、不读 graph state、不访问 checkpoint/mem0。
- helper 不重新执行旧 `rag.intent.is_user_fact_statement()` 等规则。

## 实施步骤

1. 复核 `IntentDecision.turn_type` 与 `TurnTypeDecision` 当前契约。
2. 新增最小派生 helper，避免引入宽泛新抽象。
3. 补充单元测试覆盖所有 `IntentRoute` 到 `TurnType` 的映射。
4. 保持主图仍按旧路径运行，为任务 60 切换做准备。

## 验证方案

```bash
cd agent
uv run pytest tests/test_intent_authority_contract.py tests/test_intent_contracts.py tests/test_contracts.py -v
uv run ruff check src tests
```

## 非范围

- 不修改 `load_memory`。
- 不删除旧 `classify_turn_type()`。
- 不改变 rewrite/router/executor 行为。
- 不更新 README 当前运行契约。

## 完成标准

- [ ] 存在明确的 `IntentDecision` -> `TurnTypeDecision` 派生入口。
- [ ] 派生入口有完整 route 覆盖测试。
- [ ] 主图行为不变。
- [ ] 验证命令通过。
- [ ] `docs/progress.md` 更新。

## 进度更新

`docs/progress.md` **59** → 实现完成后改为 `✅`。
