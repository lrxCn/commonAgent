# 07 - mem0 读取

## 依赖

02, 04

## 目标

对话开始时按 `user_id` 从 **本地 mem0（OSS SDK）+ 本地 Qdrant** 拉取用户偏好（提取式事实），供后续注入 system。

## 范围

- `agent/src/memory/mem0_client.py`：
  - `fetch_user_memories(user_id) -> list[str]`
  - `afetch_user_memories(user_id)` — 与 checkpoint 并行用（`asyncio.to_thread` 即可）
  - `format_mem0_for_system(memories) -> str`
- `agent/.env.example` 增加 mem0/Qdrant 相关 key（见下）
- `agent/src/settings/config.py` 映射：`MEM0_MOCK`、`QDRANT_COLLECTION_MEM0`、`MEM0_READ_LIMIT` 等

## 非范围

- 写入（任务 **17**）
- **mem0 托管云 / MemoryClient / `MEM0_API_KEY` / `api.mem0.ai`** — 第一期 **禁止**

## 部署约束（必读，避免误实现）

| 必须 | 禁止 |
|------|------|
| `from mem0 import Memory`（或 `AsyncMemory`）自托管 | `from mem0 import MemoryClient` |
| 向量库：`vector_store.provider = "qdrant"`，连 **`QDRANT_HOST` + `QDRANT_PORT`** | 连 mem0 云端 API |
| 独立 collection：`QDRANT_COLLECTION_MEM0`（与 `QDRANT_COLLECTION_KB` 分开） | 与 KB 共用一个 collection |
| LLM/Embedding：复用现有 `OPENAI_*` + `EMBEDDING_*`（SiliconFlow 兼容） | 为 mem0 单独引入云端 mem0 账号 |

**无本地 Qdrant / 不想连真库时**：`MEM0_MOCK=true` → `fetch_user_memories` 直接返回 `[]`（CI 默认）。这不是「走云端」，只是跳过读取。

## 实现要点

- 提取式事实语义；不存整段对话
- `Memory.from_config(...)` 或等价构造；`get_all(user_id=...)` 取回后解析 `memory` 字段为 `list[str]`
- 空/缺 `user_id` → 抛明确异常（如 `Mem0UserIdError`）
- 单测 **mock** `Memory.get_all` 或注入 fetch override，**不要**在 CI 依赖外网或 mem0 云

## 环境变量（写入 `.env.example`）

```bash
# --- mem0（本地 OSS + Qdrant；勿配置 MEM0_API_KEY）---
MEM0_MOCK=true
QDRANT_COLLECTION_MEM0=common_agent_mem0
MEM0_READ_LIMIT=50
```

## 测试方案

```bash
cd agent
uv run pytest tests/test_mem0_read.py -v
```

用例：正常 `user_id` + mock `get_all` 返回事实列表；`format_mem0_for_system` 含 bullet；无 `user_id` 抛错；`MEM0_MOCK=true` 返回空列表；`afetch_user_memories` 可 await。

## 完成标准

- 仅本地 `Memory` + Qdrant；代码与依赖中 **无** `MemoryClient` / `MEM0_API_KEY`
- 接口稳定，供任务 09/12/13 调用
- mock 模式 CI 可跑通

## 进度更新

`docs/progress.md` **07** → `✅`
