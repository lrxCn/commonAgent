# 63 - 结构化记忆写入 Phase 0：契约与评测种子

## 建议执行模型

- 模型：GPT-5.4
- Reasoning：high
- 原因：定义后续写入路径重构的核心契约与 eval 口径，虽不改运行行为，但决定类型边界与验收标准。

## 新窗口执行规则

1. 先读根目录 `AGENTS.md`、`README.md`、`docs/progress.md` 和本任务卡。
2. 阅读 PRD：[agent-structured-memory-write.md](../prd/agent-structured-memory-write.md)。
3. 核对 `docs/progress.md` 中本任务依赖是否完成；未完成则停止。
4. 对比当前模型和 reasoning 与本节建议；如果不一致或未知，先告诉用户建议配置并等待确认，除非用户明确要求继续。
5. 只实现本任务范围，不顺手做相邻任务。
6. 按本任务测试计划验证。
7. 测试通过后更新 `docs/progress.md`。
8. 自动创建 git commit；不要自动 push，除非用户明确要求。

## 依赖

62

## 背景

PRD：[Agent 结构化记忆写入（Single Extraction Point）](../prd/agent-structured-memory-write.md) 要求 Policy 通过的 `fact_update` 走控制面单次 slot fill + 存储面 deterministic upsert。当前 post_turn 仍统一 `infer=True`，存在 `stored_empty` 与用户 Commit 不一致问题。

本任务只做契约与 eval 先行，**不改变 graph 运行路径**。

## 目标

- 新增 `StructuredMemoryRecord` 及相关枚举契约。
- 新增 `memory_write_seed.json` 与 README 说明。
- 新增行为冻结测试：记录当前 fact_update + infer 路径下 `stored_empty` 可复现（mock）。
- 为任务 64-67 提供稳定类型与验收口径。

## 范围

| 模块 | 变更 |
|------|------|
| `agent/src/contracts/memory_write.py` | 新增 `MemorySubject`、`StructuredMemoryRecord`、`MemoryWriteMode` 等 |
| `agent/src/contracts/__init__.py` | 导出（如项目惯例需要） |
| `agent/evals/memory_write_seed.json` | 结构化写入 eval seed |
| `agent/evals/README.md` | 补充 memory_write seed 用途与运行说明 |
| `agent/tests/test_memory_write_contracts.py` | 契约序列化、字段校验 |
| `agent/tests/test_memory_write_eval_seed.py` | seed 结构与必备样例 |
| `agent/tests/test_structured_memory_characterization.py` | 冻结当前 infer 路径行为（含 store_empty 样例） |
| `docs/progress.md` | 本任务状态 |

## StructuredMemoryRecord 最小字段

```python
StructuredMemoryRecord(
    subject="user",
    attribute="name",
    value="张三",
    raw_utterance="我叫张三",
    confidence=0.94,
    source_turn_id="thread-1:turn-3",
    extraction_method="slot_fill_v1",
)
```

## memory_write_seed 必须覆盖

| 类别 | 必备样例 | 预期（目标态，本任务仅写 seed 字段） |
|------|----------|--------------------------------------|
| `structured_fact_update` | 我叫张三 / 我出生于1997年 / 我公司在天翔街188号 | mode=structured, infer=false |
| `inferred_general_chat` | 闲聊中顺带偏好 | mode=inferred, infer=true |
| `regression_store_empty` | Policy 通过 fact_update | 不得 final_status=stored_empty |

## 非范围

- 不实现 slot fill 逻辑（任务 64）。
- 不改 `mem0_write.py` 生产路径（任务 65）。
- 不接 graph / post_turn（任务 66）。
- 不更新 README 运行契约（任务 68）。
- 不改用户确认模板（任务 67）。

## 验证方案

```bash
cd agent
uv run pytest tests/test_memory_write_contracts.py tests/test_memory_write_eval_seed.py tests/test_structured_memory_characterization.py -v
```

## 完成标准

- [ ] 契约 frozen model 可被后续模块 import。
- [ ] memory_write seed 覆盖 PRD 表格样例。
- [ ] characterization 测试记录当前 infer 路径行为（作为重构前基线）。
- [ ] `docs/progress.md` 任务 63 标记完成。

## 进度更新

`docs/progress.md` **63** → 实现完成后改为 `✅`。
