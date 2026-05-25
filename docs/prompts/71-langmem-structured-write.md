# 71 - LangMem 迁移 Phase 2：Structured Write 切 Store

## 建议执行模型

- 模型：GPT-5.4
- Reasoning：high
- 原因：fact_update 快路径 deterministic upsert 是 Single Extraction Point 的核心；须保持 eval 与 memory_query 不回退。

## 新窗口执行规则

1. 先读 PRD [agent-langmem-migration.md](../prd/agent-langmem-migration.md) 与任务 70 产出。
2. 核对任务 **70** 完成。
3. 只改 structured write；inferred 仍走 mem0（任务 72）。
4. 测试通过后更新 `docs/progress.md`。

## 依赖

70

## 背景

Policy 通过的 `fact_update` 已在控制面产出 `StructuredMemoryRecord`，post_turn 调用 `store_structured_record()`。当前实现经 mem0 `Memory.add(..., infer=False)`。本任务改为 **Store profile namespace 直接 put**，不再调用 mem0 write API。

## 目标

- 新增或扩展 `memory/write.py`：`store_structured_record(user_id, record) -> MemoryWriteResult`（可复用 `Mem0WriteResult` 形状或重命名为 `MemoryWriteResult`）。
- Profile key = `record.attribute`；value = 契约 JSON（含 canonical 文本字段）。
- `MEMORY_STORE_MOCK` 下返回可预测 stored。
- Trace：写入 `memory_store.status`、`memory_write.mode=structured`；**并行**保留 `mem0_write.*` 键一个版本（任务 74 删旧键）。
- `ExtractionMethod`：新增 `LANGMEM_STORE` 或 `STORE_PROFILE`；`MEM0_INFER` 保留至任务 72/73。
- Eval：`memory_write_seed.json` structured 用例在 Store mock 下 **不得** `stored_empty`。

## 范围

| 模块 | 变更 |
|------|------|
| `agent/src/memory/write.py` | `store_structured_record` |
| `agent/src/memory/mem0_write.py` | delegate 到 write.py 或 thin wrapper（任务 73 删） |
| `agent/src/memory/post_turn.py` | import 新 write |
| `agent/src/contracts/memory_write.py` | extraction_method enum 扩展 |
| `agent/src/observability/path_contract.py` | 如有 mem0 专有键则增 Store 键 |
| `agent/tests/test_memory_store_write.py` | structured 单测（自 `test_mem0_write` 迁移 structured 部分） |
| `agent/scripts/run_memory_write_eval.py` | structured 路径对 Store 生效 |

## 写入示例（概念）

```python
store.put(
    ("users", user_id, "profile"),
    record.attribute,
    {
        "value": record.value,
        "raw_utterance": record.raw_utterance,
        "source_turn_id": record.source_turn_id,
        "extraction_method": record.extraction_method,
        "canonical": canonical_fact_text(record),
    },
)
```

## 非范围

- 不切换 inferred write（任务 72）。
- 不删 `mem0_client` / mem0 infer（任务 73）。
- 不改 `user_memories` 字段名（任务 74）。

## 验证方案

```bash
cd agent
uv run pytest tests/test_memory_store_write.py tests/test_post_turn_graph.py tests/test_fact_update_fast_path.py -v
uv run pytest tests/test_structured_memory_characterization.py tests/test_memory_write_contracts.py -v
uv run python scripts/run_memory_write_eval.py
```

## 完成标准

- [ ] fact_update post_turn 不再调用 mem0 `Memory.add`（structured 路径）。
- [ ] 写入后 `fetch_user_memories` 可读回 profile 对应 fact。
- [ ] memory_write eval structured 样例 pass；Policy 通过样例 forbidden `stored_empty`。
- [ ] path/trace 含 `memory_write.mode=structured`。

## 进度更新

`docs/progress.md` **71** → 实现完成后改为 `✅`。
