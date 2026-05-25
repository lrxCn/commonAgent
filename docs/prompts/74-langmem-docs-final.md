# 74 - LangMem 迁移 Phase 5：README、命名收口与文档最终对齐

## 建议执行模型

- 模型：GPT-5.4
- Reasoning：medium
- 原因：文档与 state 重命名影响面大，需与 69-73 落地代码、PRD 决策一致。

## 新窗口执行规则

1. 核对任务 **73** 完成。
2. 只文档与命名收口 + 必要代码重命名；不新增记忆功能。
3. README 只写当前已落地事实。
4. 测试全绿后更新 `docs/progress.md` 与 PRD 落地状态。

## 依赖

73

## 背景

LangMem 迁移完成后，运行契约从 mem0+Qdrant 用户记忆变为 **LangGraph Postgres Store + langmem**，Profile/Collection 共存，pgvector 必开（运维见任务 75）。

本任务同步 README、maps、AGENTS、PRD 落地章节，并完成 **`mem0_memories` → `user_memories`** state 重命名（不保留长期 alias）。

## 目标

- **README.md**：记忆分层、写入双轨、Store namespace、环境变量表、本地 Postgres+pgvector 指向。
- **AGENTS.md**：Core Constraints 中 mem0 条款改为 Store/langmem；禁止第三方托管记忆 SaaS（泛化表述）。
- **docs/maps/**：`chat-turn-pipeline.md`、`state-fields.md`、`llm-calls.md`、`failure-modes.md` 等。
- **docs/prd/agent-langmem-migration.md**：落地状态与偏差章节。
- **docs/prd/agent-structured-memory-write.md**：存储面已迁 Store 的说明。
- **issue/mem0事实抽取失败.md**：标注已通过 structured + langmem 迁移解决。
- State：`AgentState.mem0_memories` → `user_memories`；更新 graph、assembly、rewrite、query、tests、trace metadata。
- 函数重命名：`format_mem0_for_system` → `format_user_memories_for_system`（或等价）。
- Context budget：`MEM0_FREE_TEXT_MAX_FACTS` → `MEMORY_FREE_TEXT_MAX_FACTS`（若 73 未改完则本任务完成）。

## 范围

| 模块 | 变更 |
|------|------|
| `README.md` | 记忆与 env |
| `AGENTS.md` | 约束 |
| `docs/maps/*.md` | 导航 |
| `docs/prd/agent-langmem-migration.md` | 落地状态 |
| `docs/prd/agent-structured-memory-write.md` | 偏差 |
| `issue/mem0事实抽取失败.md` | 关闭说明 |
| `agent/src/graph/state.py` | `user_memories` |
| `agent/src/**` | 字段与函数重命名 |
| `agent/evals/README.md` | eval 说明 |
| `docs/progress.md` | 69-74、75 收口与 changelog |

## 文档原则

- README = 当前事实；PRD = 设计 + 落地状态。
- maps 不引入 README 未声明的新契约。
- 不删除历史 prompt 卡 07/17/24 等；可选加一行 superseded 说明。

## 验证方案

```bash
cd agent
uv run pytest tests/ -v -m "not integration"
rg -n "mem0_memories|MEM0_|mem0 OSS|QDRANT_COLLECTION_MEM0" README.md AGENTS.md agent/src docs/maps
rg -n "user_memories|MEMORY_STORE|langmem|LangGraph Store" README.md docs/maps
```

## 非范围

- 不新增 hot-path memory tools。
- 不改 Front/Back API。
- 不修改根文档治理顺序（AGENTS 优先级）。

## 完成标准

- [ ] README 描述 Store + langmem + Profile/Collection + pgvector 当前事实。
- [ ] 代码与文档无 `mem0_memories` / 运行时 `MEM0_*`。
- [ ] PRD 落地状态与 README 一致。
- [ ] progress 69-74 全部 ✅；LangMem 迁移批次收口。
- [ ] 非 integration 测试全绿。

## 进度更新

`docs/progress.md` **74** → 实现完成后改为 `✅`；总览「已完成」更新为 75（若 75 亦完成）。
