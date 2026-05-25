# 69 - LangMem 迁移 Phase 0：契约、行为冻结与依赖 Spike

## 建议执行模型

- 模型：GPT-5.4
- Reasoning：high
- 原因：定义 Store 读取契约、冻结 mem0 基线行为，并验证 langmem / Postgres Store 与现有 checkpoint 版本兼容；**不改生产热路径**。

## 新窗口执行规则

1. 先读根目录 `AGENTS.md`、`README.md`、`docs/progress.md` 和本任务卡。
2. 阅读 PRD：[agent-langmem-migration.md](../prd/agent-langmem-migration.md)。
3. 核对 `docs/progress.md` 中任务 68 是否完成；未完成则停止。
4. 对比当前模型和 reasoning 与本节建议；如果不一致或未知，先告诉用户建议配置并等待确认，除非用户明确要求继续。
5. 只实现本任务范围，不顺手做 Store 读写的生产接入（任务 70）。
6. 按本任务测试计划验证。
7. 测试通过后更新 `docs/progress.md`。
8. 自动创建 git commit；不要自动 push，除非用户明确要求。

## 依赖

68

## 背景

PRD：[LangMem 迁移](../prd/agent-langmem-migration.md) 要求用 LangGraph Store + langmem 替换 mem0。任务 70 起才改读写路径；本任务先定契约、冻结行为、验证依赖矩阵。

**已确认**：无过渡期；Qdrant mem0 数据可丢；Profile + Collection 共存且 collection 需 pgvector（任务 75）。

## 目标

- 扩展或新增 Store 相关 typed contracts（namespace、profile value、读取结果形状）。
- 新增 characterization 测试：冻结 `load_memory` fact 列表形状、post_turn structured/inferred 互斥、memory_query 证据来源（仍走 mem0 实现）。
- Spike：`uv add langmem` 与 Postgres Store 包（以 spike 结论写入 PRD 或本任务备注的包名），本地验证 `store.setup()` 与 checkpoint **同库**不冲突。
- Pin `langmem>=0.0.30`（或 spike 验证通过的版本）到 `pyproject.toml`；**本任务不删除 mem0**。

## 范围

| 模块 | 变更 |
|------|------|
| `agent/pyproject.toml` / `uv.lock` | 添加 `langmem`、Store postgres 包（spike 确认包名） |
| `agent/src/contracts/memory_store.py`（或扩展 `memory_write.py`） | `MemoryStoreNamespace`、`ProfileMemoryValue`、`UserMemoryReadResult` 等最小契约 |
| `agent/src/contracts/__init__.py` | 导出（如惯例需要） |
| `agent/tests/test_memory_store_contracts.py` | 契约校验与 namespace 常量 |
| `agent/tests/test_langmem_migration_characterization.py` | 冻结 mem0 时代读写行为基线 |
| `agent/tests/test_langmem_store_spike.py` | 可选 integration：Postgres + pgvector 下 `setup()` smoke（无 pgvector 则 skip 并注明依赖 75） |
| `docs/progress.md` | 本任务状态；spike 包名结论 |

## Store namespace 约定（写入契约，供 70+ 使用）

| 用途 | namespace |
|------|-----------|
| Profile 结构化 | `("users", user_id, "profile")` |
| Collection 自由文本 | `("users", user_id, "facts")` |

Profile value 最小字段：`value`, `raw_utterance`, `source_turn_id`, `extraction_method`, `updated_at`（ISO 字符串）。

读取契约：`fetch_user_memories` 目标返回 `list[str]`（canonical fact 文本），由 profile 合成 + collection 条目合并（任务 70 实现）。

## Characterization 必须覆盖

| 场景 | 冻结点 |
|------|--------|
| `load_memory_node` | 产出 `mem0_memories: list[str]`；并行 fetch checkpoint summary |
| post_turn + `memory_write_record` | 只调 structured write，不调 infer |
| post_turn 无 record | 调 inferred write |
| `memory_query` | 不调度 mem0 write |
| fact_update structured | eval seed 期望 `stored_empty` forbidden（相对 Policy 通过样例） |

## 非范围

- 不实现 `memory/store.py` / `memory/read.py` 生产逻辑（任务 70）。
- 不切换 `fetch_user_memories` 默认后端（任务 70）。
- 不删 mem0、不改 README 运行契约（任务 74）。
- 不写 Qdrant → Store 迁移脚本。

## 验证方案

```bash
cd agent
uv run pytest tests/test_memory_store_contracts.py tests/test_langmem_migration_characterization.py -v
# 有 Postgres + pgvector 时：
uv run pytest tests/test_langmem_store_spike.py -v -m integration
uv run pytest tests/test_memory_write_contracts.py tests/test_structured_memory_characterization.py -v
```

## 完成标准

- [ ] Store 相关契约可被 70+ import。
- [ ] characterization 测试在 mem0 实现下绿，作为迁移前基线。
- [ ] spike 记录：Store 包名、与 `langgraph-checkpoint-postgres` 共存结论。
- [ ] `docs/progress.md` 任务 69 标记完成。

## 进度更新

`docs/progress.md` **69** → 实现完成后改为 `✅`。
