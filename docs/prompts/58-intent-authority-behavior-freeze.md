# 58 - 意图权威收敛 Phase 0：行为冻结与双轨分歧审计

## 建议执行模型

- 模型：GPT-5.5
- Reasoning：high
- 原因：本任务为后续切换权威分类来源建立测试护栏，需要准确识别旧 `turn_type` 与新 `IntentDecision` 的分歧，避免后续重构把目标行为和回归混在一起。

## 新窗口执行规则

1. 先读根目录 `AGENTS.md`、`README.md`、`docs/progress.md` 和本任务卡。
2. 核对 `docs/progress.md` 中本任务依赖是否完成；未完成则停止。
3. 对比当前模型和 reasoning 与本节建议；如果不一致或未知，先告诉用户建议配置并等待确认，除非用户明确要求继续。
4. 只实现本任务范围，不顺手做相邻任务。
5. 按本任务测试计划验证。
6. 测试通过后更新 `docs/progress.md`。

## 依赖

57

## 背景

当前系统同时存在旧兼容分类 `graph.turn_type.classify_turn_type()` 和新控制面分类 `intent.engine.classify_intent()`。后续要把 `IntentDecision` 变成唯一权威，第一步必须冻结当前双轨表现，并明确目标行为。

## 目标

- 新增行为冻结测试，列出典型输入下旧 `turn_type`、新 `IntentDecision.route` 和目标路径。
- 明确哪些分歧是预期修正，例如第一人称疑问从旧 `fact_update` 迁移到 `memory_query`。
- 不改变运行时代码路径。

## 范围

| 模块 | 变更 |
|------|------|
| `agent/tests/test_intent_authority_characterization.py` | 新增双轨分歧矩阵和目标行为断言 |
| `agent/evals/intent_seed.json` | 如缺少关键样例，补充最小 seed 行 |
| `agent/evals/README.md` | 如 seed 语义变化，补充说明 |
| `docs/progress.md` | 本任务完成后更新状态和日志 |

## 必须覆盖的样例

```text
我是谁
我叫什么
我的名字是什么
我公司在哪
我喜欢什么
我叫张三
我公司在天翔街188号
报销制度是什么
打开 pageA
它需要什么材料
你好
```

## 实施步骤

1. 阅读 `agent/src/graph/turn_type.py`、`agent/src/intent/engine.py`、`agent/src/contracts/intent.py` 和现有 intent/path 测试。
2. 新增 characterization 测试，同时调用旧 `classify_turn_type()` 与新 `classify_intent()`。
3. 对分歧样例写明 `target_route` / `target_turn_type`，后续任务以目标行为为准。
4. 如 seed 缺少目标样例，只补最小必要行，不扩大评测体系。

## 验证方案

```bash
cd agent
uv run pytest tests/test_intent_authority_characterization.py tests/test_intent_eval_seed.py -v
uv run python scripts/run_intent_eval.py --seed evals/intent_seed.json --json
uv run ruff check src tests
```

## 非范围

- 不修改 `load_memory`。
- 不改变 `classify_turn_type()` 实现。
- 不重写 intent rules。
- 不更新 README 当前运行契约。

## 完成标准

- [ ] 双轨分歧矩阵有测试覆盖。
- [ ] 目标行为明确，特别是第一人称疑问目标为 `memory_query`。
- [ ] 运行时行为不变。
- [ ] 验证命令通过。
- [ ] `docs/progress.md` 更新。

## 进度更新

`docs/progress.md` **58** → 实现完成后改为 `✅`。
