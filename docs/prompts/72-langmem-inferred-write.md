# 72 - LangMem 迁移 Phase 3：Inferred Write 切 langmem

## 建议执行模型

- 模型：GPT-5.4
- Reasoning：high
- 原因：langmem store manager 接入 LLM Gateway、instructions 与 post_turn 异步语义需要对齐现有 inferred 慢路径。

## 新窗口执行规则

1. 先读 PRD 与任务 71 产出。
2. 核对任务 **71** 完成。
3. 只替换 inferred 慢路径；structured 保持 Store put（任务 71）。
4. 环境契约：`MEMORY_EXTRACT_*` 新增并保留 `MEM0_LLM_*` alias 至任务 74。
5. 测试通过后更新 `docs/progress.md`。

## 依赖

71

## 背景

非 fact_update structured 的 post_turn 回合（如 chitchat）当前调用 `extract_and_store(..., infer=True)`，由 mem0 内置 LLM 抽取。本任务改为 **langmem `create_memory_store_manager`**，namespace `("users", user_id, "facts")`，结果写入 Collection（pgvector index 由任务 70 配置）。

## 目标

- `memory/langmem_manager.py`（或 write.py 内）：封装 singleton `get_memory_store_manager()`。
- `memory/write.py`：`extract_and_store(user_id, turn_messages) -> MemoryWriteResult` 改调 manager.invoke。
- `ModelUseCase.MEM0_WRITE` → **`MEMORY_EXTRACT`**（保留 enum alias `MEM0_WRITE` 至任务 74）。
- `infrastructure/llm/policy.py`：MEMORY_EXTRACT 模型策略（默认接原 MEM0 小模型 env）。
- 迁移 `memory/prompts/mem0_custom_instructions.txt` → `memory/prompts/memory_extract_instructions.txt`（或等价）。
- post_turn 双轨互斥不变：有 `memory_write_record` 时不 invoke manager。
- Trace：`memory_write.mode=inferred`、`memory_store.stored_count` 等。

## 范围

| 模块 | 变更 |
|------|------|
| `agent/src/memory/langmem_manager.py` | manager 工厂 |
| `agent/src/memory/write.py` | `extract_and_store` |
| `agent/src/memory/post_turn.py` | 调用 write.extract_and_store |
| `agent/src/contracts/llm.py` | `MEMORY_EXTRACT` |
| `agent/src/infrastructure/llm/policy.py` | 策略映射 |
| `agent/src/settings/config.py` | `MEMORY_EXTRACT_MODEL_NAME` 等 |
| `agent/.env.example` | 新变量 |
| `agent/tests/test_memory_store_write.py` | inferred 单测 |
| `agent/tests/test_llm_gateway.py` | ModelUseCase 更新 |

## 行为说明

- inferred 路径 **允许** `stored_empty`（by design）；须 trace manager 返回条数。
- 不得对 Policy 通过的 fact_update structured 路径调用 manager（由 71 + post_turn 保证）。
- `memory_query` 回合仍 skip write。

## 非范围

- 不删 mem0 依赖与 dead code（任务 73）。
- 不引入 hot-path `create_manage_memory_tool` 给 deepagents。
- 不改 README（任务 74）。

## 验证方案

```bash
cd agent
uv run pytest tests/test_memory_store_write.py tests/test_post_turn_graph.py tests/test_llm_gateway.py -v
uv run pytest tests/test_settings.py::test_env_files_match_settings_contract -v
```

## 完成标准

- [ ] post_turn inferred 路径不再调用 mem0 `Memory.add(infer=True)`。
- [ ] manager 使用 LLM Gateway / MEMORY_EXTRACT 配置。
- [ ] collection 写入后，`fetch_user_memories` search 可召回（mock 或 integration）。
- [ ] structured / inferred 互斥测试仍 pass。

## 进度更新

`docs/progress.md` **72** → 实现完成后改为 `✅`。
