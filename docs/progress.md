# 通用 Agent 实现进度

> **维护方式**：执行 `docs/prompts/` 任务卡时由 Cursor skill [execute-prompt-task](../.cursor/skills/execute-prompt-task/SKILL.md) 在测试通过后更新本文。人工改代码时也请同步更新对应行。

**架构**：[architecture.md](./architecture.md) · **需求**：[prd1.md](./prd1.md)

## 总览

| 指标 | 值 |
|------|-----|
| 总任务数 | 24 |
| 已完成 | 23 |
| 进行中 | — |
| 阻塞 | 0 |

**当前建议下一步**：[23 - Front 占位](./prompts/23-front-stub.md)


---

## 任务清单

状态：`⬜ 待开始` · `🔄 进行中` · `✅ 完成` · `⏸ 阻塞` · `⏭ 跳过`

| ID | 任务 | 状态 | 完成时间 | 备注 |
|----|------|------|--------|------|
| 01 | [项目骨架与 uv/deepagents 初始化](./prompts/01-project-init.md) | ✅ | 2026-05-19 | deepagents-python 模板；根 `.gitignore`；`agent/.env.example` 统一契约 |
| 02 | [配置层 settings + .env 契约](./prompts/02-agent-settings.md) | ✅ | 2026-05-19 | `agent/src/settings/config.py`；`pydantic-settings`；`LANGCHAIN_API_KEY` fallback |
| 03 | [Postgres Checkpointer](./prompts/03-postgres-checkpointer.md) | ✅ | 2026-05-19 | `memory/checkpointer.py`；README 本地 Postgres 说明；`langgraph-checkpoint-postgres` |
| 04 | [请求 Context 模型](./prompts/04-request-context-models.md) | ✅ | 2026-05-19 | `gateway/schemas.py`；`test_schemas.py` 6 用例 |
| 05 | [Gateway 最小骨架](./prompts/05-gateway-minimal.md) | ✅ | 2026-05-19 | `gateway/app.py`、`main.py`；FastAPI health + chat stub |
| 06 | [入站护栏](./prompts/06-guardrails-inbound.md) | ✅ | 2026-05-19 | `guardrails/inbound.py`；`GUARDRAILS_ENABLED`；Gateway 400；7 用例 |
| 07 | [mem0 读取](./prompts/07-mem0-read.md) | ✅ | 2026-05-19 | `memory/mem0_client.py`；`MEM0_MOCK`；`test_mem0_read.py` 9 用例 |
| 08 | [Checkpoint 历史读取](./prompts/08-checkpoint-history-read.md) | ✅ | 2026-05-19 | `memory/history.py`；`ROLLING_SUMMARY_METADATA_KEY`；`test_history.py` 10 用例 |
| 09 | [Query Rewrite](./prompts/09-query-rewrite.md) | ✅ | 2026-05-19 | `rag/rewrite.py`；`REWRITE_MODEL_NAME`；`rewrite_node`；`test_rewrite.py` 9 用例 |
| 10 | [RAG 路由](./prompts/10-rag-router.md) | ✅ | 2026-05-19 | `rag/router.py`；`RAG_ROUTER_MODE`；`rag_router_node`；`test_rag_router.py` 16 用例 |
| 11 | [RAG 检索管线](./prompts/11-rag-retrieval.md) | ✅ | 2026-05-19 | `rag/retriever.py`；`QDRANT_MOCK`；`test_rag_retrieval.py` 12 用例 |
| 12 | [上下文组装 K+M+summary](./prompts/12-context-assembly.md) | ✅ | 2026-05-19 | `memory/assembly.py`；`build_context`；`test_context_assembly.py` 9 用例 |
| 13 | [Supervisor 主图](./prompts/13-supervisor-graph.md) | ✅ | 2026-05-19 | `graph/` state+nodes+build+supervisor；`langgraph.json`→`get_graph`；mock 测试 5 用例 |
| 13.5 | [State 与 context_schema 拆分](./prompts/13.5_fix_state_2_context_schema.md) | ✅ | 2026-05-19 | `graph/context.py`；`EphemeralValue` + 节点内 carry；`invoke(context=)` |
| 14 | [RagSubAgent 二查](./prompts/14-rag-subagent.md) | ✅ | 2026-05-19 | `graph/rag_subagent.py`；条件边；`RAG_SUBAGENT_*`；`test_rag_subagent.py` 13 用例 |
| 15 | [出站护栏](./prompts/15-guardrails-outbound.md) | ✅ | 2026-05-19 | `guardrails/outbound.py`；`outbound_guard` 节点；`test_guardrails_outbound.py` 7 用例 |
| 16 | [client_actions 输出契约](./prompts/16-client-actions-schema.md) | ✅ | 2026-05-19 | `graph/client_actions.py`；`client_actions_emit` 节点；Gateway stub JSON；`test_client_actions.py` 8 用例 |
| 17 | [异步 Summary + mem0 写入](./prompts/17-async-summary-mem0.md) | ✅ | 2026-05-19 | `summary_job.py`、`mem0_write.py`、`post_turn.py`；`post_turn_jobs` 节点；`test_summary_job` 5 + `test_mem0_write` 5 用例 |
| 18 | [Chat SSE API](./prompts/18-chat-sse-api.md) | ✅ | 2026-05-19 | `gateway/chat.py`；SSE token/done；client_actions JSON；`test_chat_sse.py` 5 用例 |
| 19 | [历史分页 API](./prompts/19-history-pagination-api.md) | ✅ | 2026-05-19 | `gateway/history.py`、`schemas_history.py`；offset/message_id cursor；`test_history_api.py` 7 用例 |
| 20 | [KB Ingest API](./prompts/20-kb-ingest-api.md) | ✅ | 2026-05-19 | `rag/ingest.py`；`gateway/ingest.py`；`CHUNK_*`；`test_kb_ingest.py` 6 用例 |
| 21 | [LangSmith 接入](./prompts/21-langsmith-integration.md) | ✅ | 2026-05-19 | `observability/tracing.py`；关键 span 标签；`test_tracing.py` |
| 22 | [Back 占位服务](./prompts/22-back-stub.md) | ✅ | 2026-05-19 | `back/` FastAPI；`POST /api/chat` 注入 demo context 转发 Agent；`test_back_forward.py` 6 用例 |
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
| 2026-05-19 | 完成任务 05：FastAPI Gateway `GET /health`、`POST /internal/chat` stub；`test_gateway_health.py` 3 用例 |
| 2026-05-19 | 完成任务 06：入站规则护栏 + Gateway 集成；`test_guardrails_inbound.py` 7 用例 |
| 2026-05-19 | 文档：任务 07/17、architecture §4/§10.1 明确 mem0 仅本地 OSS+Qdrant，禁止托管云 |
| 2026-05-19 | 完成任务 07：本地 mem0 读取 + Qdrant 配置；`mem0ai`/`qdrant-client`；`test_mem0_read.py` 9 用例 |
| 2026-05-19 | 完成任务 08：checkpoint 历史读取 + rolling summary；`test_history.py` 10 用例（含 integration） |
| 2026-05-19 | 完成任务 09：mem0+短期 query rewrite、`rewrite_node`；`langchain-openai`；`test_rewrite.py` 9 用例 |
| 2026-05-19 | 完成任务 10：RAG 混合路由（规则+LLM）、`rag_skipped`；`test_rag_router.py` 16 用例 |
| 2026-05-19 | 完成任务 11：`retrieve` + `rag_retrieval_node`；dense/sparse(文本回退)+rerank；`QDRANT_MOCK` fixture |
| 2026-05-19 | 完成任务 12：`build_context` K+M+summary 组装；prefix/recent 去重；`test_context_assembly.py` 9 用例 |
| 2026-05-19 | 完成任务 13：Supervisor 主图（护栏→并行 mem0/history→rewrite→RAG→组装→deepagents）；`test_graph_*.py` 5 用例 |
| 2026-05-19 | 文档：新增任务 13.5（State/context_schema 拆分）及影响面清单；architecture §3.1 |
| 2026-05-19 | 完成任务 13.5：`GraphContextSchema` + `EphemeralValue`；图测试 7 用例 |
| 2026-05-19 | 完成任务 14：RagSubAgent 规则委派二查、合并去重、`retrieve(second_pass=True)` |
| 2026-05-19 | 完成任务 15：出站整段护栏、`supervisor`→`outbound_guard`、违规安全回复 |
| 2026-05-19 | 完成任务 16：client_actions 解析/白名单校验、图分支跳过出站护栏、Gateway stub JSON |
| 2026-05-19 | 完成任务 17：增量 rolling summary + 提取式 mem0 写入；ThreadPool fire-and-forget |
| 2026-05-19 | 完成任务 18：POST /internal/chat 接图；SSE 文本流 + client_actions JSON；`test_chat_sse.py` |
| 2026-05-19 | 完成任务 19：GET /internal/threads/{id}/messages 分页；checkpoint 同源；`test_history_api.py` 7 用例 |
| 2026-05-19 | 完成任务 20：POST /internal/kb/ingest；分块+embedding+按 doc_name 删旧；`test_kb_ingest.py` 6 用例 |
| 2026-05-19 | 完成任务 21：`observability/tracing.py`；rewrite/router/retrieve/rerank/supervisor/guardrails span；README LangSmith 查看说明 |
| 2026-05-19 | 完成任务 22：`back/` 占位网关；demo context + 转发 `/internal/chat`；respx mock 测试 6 用例 |
