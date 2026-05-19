# 通用 Agent 实现进度

> **维护方式**：执行 `docs/prompts/` 任务卡时由 Cursor skill [execute-prompt-task](../.cursor/skills/execute-prompt-task/SKILL.md) 在测试通过后更新本文。人工改代码时也请同步更新对应行。

**架构**：[architecture.md](./architecture.md) · **需求**：[prd1.md](./prd1.md)

## 总览

| 指标 | 值 |
|------|-----|
| 总任务数 | 23 |
| 已完成 | 4 |
| 进行中 | — |
| 阻塞 | 0 |

**当前建议下一步**：[05 - Gateway 最小骨架](./prompts/05-gateway-minimal.md)


---

## 任务清单

状态：`⬜ 待开始` · `🔄 进行中` · `✅ 完成` · `⏸ 阻塞` · `⏭ 跳过`

| ID | 任务 | 状态 | 完成时间 | 备注 |
|----|------|------|--------|------|
| 01 | [项目骨架与 uv/deepagents 初始化](./prompts/01-project-init.md) | ✅ | 2026-05-19 | deepagents-python 模板；根 `.gitignore`；`agent/.env.example` 统一契约 |
| 02 | [配置层 settings + .env 契约](./prompts/02-agent-settings.md) | ✅ | 2026-05-19 | `agent/src/settings/config.py`；`pydantic-settings`；`LANGCHAIN_API_KEY` fallback |
| 03 | [Postgres Checkpointer](./prompts/03-postgres-checkpointer.md) | ✅ | 2026-05-19 | `memory/checkpointer.py`；README 本地 Postgres 说明；`langgraph-checkpoint-postgres` |
| 04 | [请求 Context 模型](./prompts/04-request-context-models.md) | ✅ | 2026-05-19 | `gateway/schemas.py`；`test_schemas.py` 6 用例 |
| 05 | [Gateway 最小骨架](./prompts/05-gateway-minimal.md) | ⬜ | | |
| 06 | [入站护栏](./prompts/06-guardrails-inbound.md) | ⬜ | | |
| 07 | [mem0 读取](./prompts/07-mem0-read.md) | ⬜ | | |
| 08 | [Checkpoint 历史读取](./prompts/08-checkpoint-history-read.md) | ⬜ | | |
| 09 | [Query Rewrite](./prompts/09-query-rewrite.md) | ⬜ | | |
| 10 | [RAG 路由](./prompts/10-rag-router.md) | ⬜ | | |
| 11 | [RAG 检索管线](./prompts/11-rag-retrieval.md) | ⬜ | | |
| 12 | [上下文组装 K+M+summary](./prompts/12-context-assembly.md) | ⬜ | | |
| 13 | [Supervisor 主图](./prompts/13-supervisor-graph.md) | ⬜ | | |
| 14 | [RagSubAgent 二查](./prompts/14-rag-subagent.md) | ⬜ | | |
| 15 | [出站护栏](./prompts/15-guardrails-outbound.md) | ⬜ | | |
| 16 | [client_actions 输出契约](./prompts/16-client-actions-schema.md) | ⬜ | | |
| 17 | [异步 Summary + mem0 写入](./prompts/17-async-summary-mem0.md) | ⬜ | | |
| 18 | [Chat SSE API](./prompts/18-chat-sse-api.md) | ⬜ | | |
| 19 | [历史分页 API](./prompts/19-history-pagination-api.md) | ⬜ | | |
| 20 | [KB Ingest API](./prompts/20-kb-ingest-api.md) | ⬜ | | |
| 21 | [LangSmith 接入](./prompts/21-langsmith-integration.md) | ⬜ | | |
| 22 | [Back 占位服务](./prompts/22-back-stub.md) | ⬜ | | |
| 23 | [Front 占位](./prompts/23-front-stub.md) | ⬜ | | |

---

## 变更日志

| 日期 | 说明 |
|------|------|
| 2026-05-19 | 初始化进度文档与 23 项任务卡 |
| 2026-05-19 | 文档：任务 01 固化 .env 契约（SiliconFlow LLM/Embedding/Rerank、LangSmith、Qdrant）；同步 architecture §10.1、任务 02 字段列表 |
| 2026-05-19 | 完成任务 01：三目录 + uv/deepagents 骨架 + `.env.example` 契约 |
| 2026-05-19 | 完成任务 02：Pydantic Settings + `get_settings()` 单例与测试 |
| 2026-05-19 | 完成任务 03：Postgres Checkpointer 工厂、集成测试 thread 往返 |
| 2026-05-19 | 完成任务 04：ChatRequest/RequestContext/ToolSpec/ClientAction/ChatResponse Pydantic 模型 |
