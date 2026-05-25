# 64 - 结构化记忆写入 Phase 1：Slot Fill 抽取器

## 建议执行模型

- 模型：GPT-5.4
- Reasoning：high
- 原因：需对齐 intent signals、Policy Gate 与 profile 字段映射，正则/规则边界多，错误会影响写入内容。

## 新窗口执行规则

1. 先读根目录 `AGENTS.md`、`README.md`、`docs/progress.md` 和本任务卡。
2. 阅读 PRD：[agent-structured-memory-write.md](../prd/agent-structured-memory-write.md)。
3. 核对任务 63 是否完成。
4. 对比当前模型和 reasoning 与本节建议；不一致或未知时先告知用户并等待确认，除非用户明确要求继续。
5. 只实现本任务范围。
6. 测试通过后更新 `docs/progress.md` 并 git commit。

## 依赖

63

## 背景

Policy 通过的 `fact_update` 已在 `intent/signals.py` 中具备 `fact_attributes` 与 `explicit_values`。本任务将其 **确定性** 映射为 `StructuredMemoryRecord`，并生成 mem0 canonical fact 文本。

## 目标

- 新增 `memory/structured_record.py`：`build_structured_memory_record(signals, intent_decision, *, source_turn_id) -> StructuredMemoryRecord | None`。
- 新增 `canonical_fact_text(record) -> str` 集中生成写入文本。
- 覆盖 name / birthday / city / job / company.address / preference 第一批属性。
- **不调用 LLM**；仅规则与 signals。

## 范围

| 模块 | 变更 |
|------|------|
| `agent/src/memory/structured_record.py` | slot fill + canonical 文本 |
| `agent/tests/test_structured_record.py` | 正例、边界、失败返回 None |
| `docs/progress.md` | 本任务状态 |

## 映射规则（必须单测）

| 输入 | subject | attribute | value 归一 |
|------|---------|-----------|------------|
| 我叫张三 | user | name | 张三 |
| 我出生于1997年 | user | birthday | 1997（birth_year） |
| 我生活在哈尔滨 | user | city | 哈尔滨 |
| 我公司在天翔街188号 | org | company.address | 天翔街188号 |
| 我喜欢简短回答 | user | preference | 简短回答 |

失败条件（返回 `None`）：

- 无 `fact_attributes` 或无 `explicit_values`
- Policy 不应通过的多属性冲突（第一批取优先级最高 attribute，见 PRD）

## 非范围

- 不调用 mem0（任务 65）。
- 不写 graph state（任务 66）。
- 不修改 `intent/signals.py` 除非发现明显 bug 且需最小修复（须记录在 progress changelog）。

## 验证方案

```bash
cd agent
uv run pytest tests/test_structured_record.py tests/test_memory_write_eval_seed.py -v
```

## 完成标准

- [ ] PRD 第一批样例全部 slot fill 成功。
- [ ] 疑问句 / 无显式值返回 `None`。
- [ ] canonical 文本稳定、可用于 profile 归一化复测。
- [ ] 无 LLM 调用。

## 进度更新

`docs/progress.md` **64** → 实现完成后改为 `✅`。
