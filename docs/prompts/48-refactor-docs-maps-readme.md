# 48 - 大重构 Phase 7：代码地图与 README 最终对齐

## 建议执行模型

- 模型：GPT-5.4
- Reasoning：medium
- 原因：主要是文档和导航整理，但需要核对重构后的真实目录、契约、测试入口和当前运行边界。

## 依赖

47

## 背景

大重构的目标之一是让人类和 AI 都能用很少上下文定位代码。完成结构迁移后，需要新增短文档地图，并将 README 从“旧目录说明”更新为“当前真实结构入口”。

本任务是文档收口任务。

## 目标

- 新增 `docs/maps/`，用短文档说明关键代码路径。
- README 同步当前真实目录结构、验证命令和重构后契约。
- progress changelog 完整记录大重构收口。
- 明确哪些 PRD 是历史/草案，哪些 README 章节是当前运行契约。
- 复核 `AGENTS.md`、`README.md`、`docs/progress.md`、`docs/prompts/`、`docs/prd/`、`docs/maps/` 的文档层级和更新机制是否一致。
- 如果要改本文档秩序或 AI 工作规则，先说明原因、替代规则、收益和风险，并取得用户同意。

## 范围

| 模块 | 变更 |
|------|------|
| `docs/maps/chat-turn-pipeline.md` | 单轮 pipeline、stage、实现文件、测试文件 |
| `docs/maps/state-fields.md` | state 字段生命周期、producer、consumer、checkpoint 行为 |
| `docs/maps/llm-calls.md` | ModelUseCase、模型配置、调用路径、timeout/fallback |
| `docs/maps/rag-flow.md` | RAG route/retrieve/merge/rerank/formatting/权限过滤 |
| `docs/maps/client-actions.md` | client_actions 生成、白名单、SSE/JSON 返回、Front/Back/Agent 边界 |
| `docs/maps/failure-modes.md` | guardrails、Qdrant、LLM、mem0、LangSmith、post_turn 失败降级 |
| `README.md` | 更新当前架构与运行入口 |
| `AGENTS.md` | 仅在 AI 工作规则或文档治理规则确实变化且用户同意后更新 |
| `docs/progress.md` | 本任务状态与变更日志 |

## 文档原则

- 每份 map 回答一个维护问题，不写成长篇 PRD。
- 每份 map 都应链接到实现文件和测试文件。
- README 只写当前事实，不再保留已迁移前的旧结构。
- PRD 可保留为设计历史，但 README 必须是当前 source of truth。
- 文档治理规则以根 `AGENTS.md` 和 README 的“文档秩序与更新机制”为准。
- 其它 AI 若认为秩序需要改进，必须先向用户说明原因并争取同意，不能静默改规则。

## 非范围

- 不改业务代码。
- 不新增运行时功能。
- 不把 docs/maps 写成任务卡。
- 不把历史 PRD 删除，除非另有明确任务。
- 不在 41-47 完成前提前把 README 改成未来结构。

## 测试/验证方案

```bash
rg -n "agent-major-refactor|chat-turn-pipeline|state-fields|llm-calls|rag-flow|client-actions|failure-modes" README.md docs
rg -n "文档秩序|Governance|Source Of Truth|source of truth|用户同意|approval" AGENTS.md README.md docs
rg -n "TODO|待补|旧结构" README.md docs/maps docs/progress.md
```

如果项目已有 Markdown lint，可额外运行；没有则人工检查链接和路径。

## 完成标准

- [ ] `docs/maps/` 至少包含 6 份代码地图。
- [ ] README 与当前重构后目录结构一致。
- [ ] README 明确当前运行契约，PRD 明确设计历史/未来规划。
- [ ] 每份 map 都包含实现入口和测试入口。
- [ ] `AGENTS.md` 与 README 的文档治理规则一致。
- [ ] README 没有描述尚未落地的未来结构。
- [ ] `docs/progress.md` 同步。

## 进度更新

`docs/progress.md` **48** → 实现完成后改为 `✅`。
