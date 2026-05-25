# 70 - LangMem 迁移 Phase 1：Store 工厂与用户记忆读路径

## 建议执行模型

- 模型：GPT-5.4
- Reasoning：high
- 原因：Postgres Store 池化、pgvector index 与 profile/collection 双路读取是后续写入的基础。

## 新窗口执行规则

1. 先读 `AGENTS.md`、`README.md`、`docs/progress.md`、本任务卡与 PRD [agent-langmem-migration.md](../prd/agent-langmem-migration.md)。
2. 核对任务 **69**、**75** 完成（或本地已按 75 启用 pgvector）；否则停止。
3. 只实现本任务范围；**写路径仍可用 mem0**（任务 71 才切 structured write）。
4. 环境契约变更同步 `config.py`、`.env.example`、`.env`；跑 `test_settings.py::test_env_files_match_settings_contract`。
5. 测试通过后更新 `docs/progress.md`。

## 依赖

69、75

## 背景

用户长期记忆读取将分为：

1. **Profile**：`store.get(("users", uid, "profile"), attribute)` → 合成 canonical fact 字符串
2. **Collection**：`store.search(("users", uid, "facts"), query=...)`（pgvector）→ 取 top-k 自由文本

本任务实现 Store 工厂与 `fetch_user_memories()` 新后端；通过 **feature flag 或并行实现 + 测试默认 Store** 接入 `load_memory`（具体切换策略：本任务末 `fetch_user_memories` 默认走 Store，mem0 仅测试 legacy 对比时可 patch）。

## 目标

- `memory/store.py`：`get_pooled_store()`、`reset_pooled_store()`（测试）、`setup()`、pgvector index（`EMBEDDING_MODEL_DIMS` + 现有 embedding 经 LLM Gateway/infrastructure）。
- `memory/read.py`：`fetch_user_memories(user_id, *, query: str | None = None)`、`profile_facts_to_strings()`、`search_collection_facts()`。
- Settings 新增：`MEMORY_STORE_MOCK`、`MEMORY_READ_LIMIT`、`MEMORY_STORE_SETUP`；**保留** `MEM0_*` 别名读取（deprecated，任务 74 删）。
- `MEMORY_STORE_MOCK=true` 时用 `InMemoryStore`（无 pgvector，collection search 可降级为空或 keyword-less list）。
- 测试：`test_memory_store_read.py`（mock + 可选 integration）。

## 范围

| 模块 | 变更 |
|------|------|
| `agent/src/memory/store.py` | Store 工厂 |
| `agent/src/memory/read.py` | 读路径 |
| `agent/src/settings/config.py` | 新 settings |
| `agent/.env.example` | 新变量与注释 |
| `agent/src/memory/mem0_client.py` | `fetch_user_memories` 可 delegate 到 read.py 或 memory_nodes 改 import（最小 diff） |
| `agent/src/graph/nodes/memory_nodes.py` | 使用新 read（可选传入当前 user message 作 collection search query） |
| `agent/tests/test_memory_store_read.py` | 读写分离的单测 |
| `agent/tests/test_mem0_read.py` | 迁移或重定向为 Store 测试（保留文件名 deprecated 一版或改 import 目标） |

## 读取语义

- `load_memory`：对 collection 的 search query 默认用**当前轮 user message**（无则空 query / 限条 list）。
- 合并 profile + collection 为 `list[str]`，顺序：profile canonical 优先，再 collection。
- 仍写入 state 字段 **`mem0_memories`**（任务 74 改名为 `user_memories`）。

## 非范围

- 不写 Store（structured/inferred）（任务 71、72）。
- 不删 mem0 模块与依赖（任务 73）。
- 不更新 README 记忆章节（任务 74）。

## 验证方案

```bash
cd agent
uv run pytest tests/test_memory_store_read.py tests/test_settings.py::test_env_files_match_settings_contract -v
uv run pytest tests/test_graph_load_memory.py tests/test_memory_query_executor.py -v
# integration（Postgres + pgvector）：
uv run pytest tests/test_memory_store_read.py -v -m integration
```

## 完成标准

- [ ] Store 工厂在同 `DATABASE_URL` 库可 `setup()`。
- [ ] pgvector index 维度与 `EMBEDDING_MODEL_DIMS` 一致。
- [ ] `fetch_user_memories` 从 Store 返回 fact 字符串列表。
- [ ] `load_memory` 集成测试/mock 通过。
- [ ] env 三文件契约测试通过。

## 进度更新

`docs/progress.md` **70** → 实现完成后改为 `✅`。
