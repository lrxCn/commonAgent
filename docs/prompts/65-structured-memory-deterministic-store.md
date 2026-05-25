# 65 - 结构化记忆写入 Phase 2：Deterministic mem0 Store

## 建议执行模型

- 模型：GPT-5.4
- Reasoning：high
- 原因：触及 mem0 集成交互、infer=False 语义与 `Mem0WriteResult` 契约扩展，需保证 mock/单测覆盖 store_empty 回归。

## 新窗口执行规则

1. 先读 `AGENTS.md`、`README.md`、`docs/progress.md`、PRD 和本任务卡。
2. 核对任务 64 是否完成。
3. 只实现本任务范围；测试通过后更新 progress 并 commit。

## 依赖

64

## 背景

slot fill 已产出 `StructuredMemoryRecord` 与 canonical 文本。本任务在 `mem0_write.py` 增加 **structured store** 入口，使用 `infer=False` 写入，不再依赖 mem0 内置抽取 LLM。

## 目标

- 新增 `store_structured_record(user_id, record) -> Mem0WriteResult`。
- 使用 `memory.add(..., infer=False)` + canonical fact（及可选 metadata）。
- 扩展 trace metadata：`memory_write.mode=structured`。
- 保留现有 `extract_and_store(..., infer=True)` 供慢路径使用。
- mock 测试：structured 路径不得 `stored_empty`（对 PRD 正例）。

## 范围

| 模块 | 变更 |
|------|------|
| `agent/src/memory/mem0_write.py` | `store_structured_record`、metadata |
| `agent/tests/test_mem0_write.py` | structured store 用例 |
| `agent/tests/test_structured_memory_characterization.py` | 更新/补充 structured 预期（若适用） |
| `docs/progress.md` | 本任务状态 |

## 行为约定

- `MEM0_MOCK=true` 时返回可预测的 mock stored 结果。
- structured 路径 **禁止** `infer=True`。
- 失败时 `status=failed` 或等价，并 log + trace；不抛到 post_turn 主线程。
- 若 mem0 `infer=False` API 与预期不符，在 progress changelog 记录偏差与选用方案。

## 非范围

- 不接 graph / post_turn 路由（任务 66）。
- 不改确认话术（任务 67）。
- 不实现 retry queue / Outbox。

## 验证方案

```bash
cd agent
uv run pytest tests/test_mem0_write.py tests/test_structured_memory_characterization.py -v
```

## 完成标准

- [ ] `store_structured_record` mock 下对 seed 正例 `stored_count >= 1`。
- [ ] trace 含 `memory_write.mode=structured`。
- [ ] `extract_and_store` infer 路径行为无回归。
- [ ] `set_mem0_add_fn` 测试注入仍可用。

## 进度更新

`docs/progress.md` **65** → 实现完成后改为 `✅`。
