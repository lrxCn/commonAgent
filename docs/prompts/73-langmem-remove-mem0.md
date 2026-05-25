# 73 - LangMem 迁移 Phase 4：删除 mem0 与 Qdrant 用户记忆配置

## 建议执行模型

- 模型：GPT-5.4
- Reasoning：medium
- 原因：删除面清晰，重点是 grep 清零、测试全绿、依赖与 env 契约一致。

## 新窗口执行规则

1. 核对任务 **72** 完成；structured + inferred 均已走 Store/langmem。
2. 只删 mem0 相关；不做 Qdrant KB 改动。
3. 全量非 integration 测试绿后再更新 progress。
4. **不提供** Qdrant mem0 数据迁移脚本（PRD 已确认数据可丢）。

## 依赖

72

## 背景

读写均已迁移后，移除 `mem0ai`、mem0 模块、mem0 专用 Qdrant collection 配置与遗留测试。RAG 仍使用 Qdrant KB collection。

## 目标

- 删除：`mem0_client.py`、`mem0_write.py`、`prompts/mem0_custom_instructions.txt`、`prompts/mem0_extract.txt`。
- `pyproject.toml` / `uv.lock`：移除 `mem0ai`。
- Settings：删除 `QDRANT_COLLECTION_MEM0`；删除或 finalize 移除 `MEM0_*`（若任务 72 仍留 alias，本任务全部删除，仅保留 `MEMORY_*`）。
- 清理全仓库 `mem0` import（`rg mem0` 仅剩历史 prompt/PRD/changelog 可接受）。
- 测试：删除 `test_mem0_read.py` / `test_mem0_write.py` 若已完全被 Store 测试替代；更新所有 patch 路径。
- `memory/__init__.py`：导出来自 `read.py` / `write.py` / `store.py`。

## 范围

| 模块 | 变更 |
|------|------|
| 删除 mem0 源文件 | 见 PRD 清理清单 |
| `agent/pyproject.toml` | 去 mem0ai |
| `agent/src/settings/config.py` | 去 MEM0_*、QDRANT_COLLECTION_MEM0 |
| `agent/.env.example` | 同步 |
| `agent/tests/*` | 迁移/删 mem0 测试 |
| `agent/src/**` | grep 清零运行时 mem0 引用 |
| `AGENTS.md` | mem0 约束改为 Store/langmem（详细措辞任务 74 可再润色，本任务至少去掉 mem0 硬约束） |

## 非范围

- 不改 README 大段记忆文档（任务 74）。
- 不改 state 字段 `mem0_memories` 命名（任务 74）。
- 不删 RAG Qdrant 代码。

## 验证方案

```bash
cd agent
uv sync
uv run pytest tests/ -v -m "not integration"
rg -n "mem0ai|from mem0|Memory\.from_config|QDRANT_COLLECTION_MEM0|MEM0_" agent/src agent/tests
# 期望 src/tests 无命中（tests 中历史 skip 注释除外）
```

## 完成标准

- [ ] 运行时无 mem0 依赖与 import。
- [ ] env 契约测试通过。
- [ ] 非 integration 测试全绿。
- [ ] RAG 测试仍 pass（Qdrant KB 未动）。

## 进度更新

`docs/progress.md` **73** → 实现完成后改为 `✅`。
