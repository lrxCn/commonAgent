# 通用 Agent 实现进度

> **维护方式**：执行 `docs/prompts/` 任务卡时遵守根目录 [AGENTS.md](../AGENTS.md)；Cursor 可通过 [execute-prompt-task](../.cursor/skills/execute-prompt-task/SKILL.md) 适配器触发。人工改代码时也请同步更新对应行。

**AI 规则**：[AGENTS.md](../AGENTS.md) · **项目入口**：[README.md](../README.md) · **需求**：[common-agent-architecture.md](./prd/common-agent-architecture.md) · **运行时优化 PRD**：[agent-runtime-optimization.md](./prd/agent-runtime-optimization.md) · **结构化记忆写入 PRD**：[agent-structured-memory-write.md](./prd/agent-structured-memory-write.md) · **LangMem 迁移 PRD**：[agent-langmem-migration.md](./prd/agent-langmem-migration.md) · **memory_query 润色 PRD**：[agent-memory-query-polish.md](./prd/agent-memory-query-polish.md) · **演示平台 PRD**：[demo-admin-console.md](./prd/demo-admin-console.md)

## 总览

**当前建议下一步**：演示平台 **83** [Front Vue3 SPA 脚手架](./prompts/83-demo-front-vue-scaffold.md) 或 **84** [Front 登录与布局](./prompts/84-demo-front-auth-layout-home.md)（84 依赖 82+83；**82** 已完成）。

| 指标 | 值 |
|------|-----|
| 总任务数 | 92（规划） |
| 已完成 | 82（01–80 Agent 核心 + 81–82 演示平台首批） |
| 进行中 | — |
| 阻塞 | 0 |

**演示平台批次（81–92）**：依赖 [demo-admin-console.md](./prd/demo-admin-console.md)；**92** 为文档收口（README、walkthrough、maps、移除 legacy static front）。


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
| 23 | [Front 占位](./prompts/23-front-stub.md) | ✅ | 2026-05-19 | `front/` 单页 HTML+JS；sessionStorage thread_id；SSE + client_actions console；Back CORS |
| 24 | [mem0 All-in（infer=True）](./prompts/24-allin-mem0.md) | ✅ | 2026-05-20 | `infer=True`+`custom_instructions`；`mem0_write.py` 原文 turn；根 README 迁移说明；`test_mem0_write` 4 用例 |
| 25 | [State 精简：移除 mem0_text](./prompts/25-state-mem0-text-cleanup.md) | ✅ | 2026-05-20 | 移除 state `mem0_text`；rewrite 内格式化；`test_graph_load_memory` + tracing metadata |
| 26 | [Rewrite 条件跳过（降延迟）](./prompts/26-rewrite-conditional-skip.md) | ✅ | 2026-05-20 | `should_rewrite`+`rag/intent.py`；`rewrite_passthrough` tracing；`test_rewrite.py` 17 用例 |
| 27 | [Rewrite / RAG Router 小模型与超时保护](./prompts/27-rewrite-router-small-model.md) | ✅ | 2026-05-21 | `Qwen/Qwen2.5-7B-Instruct`；rewrite/router max token + timeout；个人/公司事实 passthrough + router skip RAG |
| 28 | [Turn Type 路由层](./prompts/28-turn-type-routing.md) | ✅ | 2026-05-21 | 统一 `turn_type` 分类；只写 state/metadata，不改执行路径 |
| 29 | [Path Contract 路径契约与可观测性](./prompts/29-path-contract-observability.md) | ✅ | 2026-05-21 | `path_metrics` 记录 should/called、LLM 调用次数与 path contract 结果 |
| 30 | [fact_update 快速路径](./prompts/30-fact-update-fast-path.md) | ✅ | 2026-05-21 | 模板确认 + 异步 mem0；跳过 rewrite/RAG/Supervisor |
| 31 | [chitchat 轻量执行器](./prompts/31-chitchat-lightweight-executor.md) | ✅ | 2026-05-21 | 模板/小模型回复；跳过 rewrite/RAG/deepagents；新增 executor tracing |
| 32 | [rewrite/router 按 turn_type 收敛](./prompts/32-rewrite-router-turn-type-convergence.md) | ✅ | 2026-05-21 | rewrite/router 消费 `turn_type`；知识查询直进 RAG，跳过 router 小模型 |
| 33 | [Executor Router 与 deepagents 分层启用](./prompts/33-executor-router-deepagents-gating.md) | ✅ | 2026-05-21 | 新增 executor router；简单 RAG/action 走轻量路径，复杂任务保留 deepagents |
| 34 | [mem0 小模型配置与写入可观测性](./prompts/34-mem0-small-model-observability.md) | ✅ | 2026-05-21 | mem0 infer 使用专用小模型；写入结果改为结构化状态并补 trace/log |
| 35 | [memory_profile 类别化记忆视图](./prompts/35-memory-profile-schema.md) | ✅ | 2026-05-21 | 运行时归一化 name/birth_year/city/job/company.address/answer_style；过滤已归类自由文本 |
| 36 | [上下文预算控制](./prompts/36-context-budget-controls.md) | ✅ | 2026-05-21 | 为 mem0、summary、RAG、tools、messages 设置明确预算并补 trace metadata |
| 37 | [Chat 真流式 SSE](./prompts/37-chat-true-streaming-sse.md) | ✅ | 2026-05-21 | 无工具文本回合通过模型 callback 真流式输出；`client_actions` 仍结构化 |
| 38 | [流式护栏与撤回事件](./prompts/38-streaming-moderation-retraction.md) | ✅ | 2026-05-21 | optimistic streaming 增量检查；支持 `retract` / `replace` SSE 事件 |
| 39 | [LangSmith Dataset 评测集与本地 seed](./prompts/39-langsmith-dataset-evals.md) | ✅ | 2026-05-21 | 本地 seed 覆盖核心 turn type；提供 LangSmith Dataset 同步脚本与 smoke test |
| 40 | [RAG 质量提升：sparse/BM25 与评测闭环](./prompts/40-rag-quality-sparse-eval.md) | ✅ | 2026-05-21 | 本地 BM25 fallback + RAG eval seed + `role_id` 防越权评测 |
| 41 | [大重构 Phase 0：行为冻结与验证入口](./prompts/41-refactor-behavior-freeze.md) | ✅ | 2026-05-21 | 修正 Makefile 测试入口；补 state lifecycle、path characterization、SSE contract、validation entrypoint 护栏 |
| 42 | [大重构 Phase 1：契约层与类型化运行对象](./prompts/42-refactor-contracts-layer.md) | ✅ | 2026-05-21 | 新增 `contracts/`，集中 routing、execution、path、context、RAG、SSE、events 契约并保留旧导入兼容 |
| 43 | [大重构 Phase 2：ContextBundle 单一上下文来源](./prompts/43-refactor-context-bundle.md) | ✅ | 2026-05-22 | 模型 system/messages/budget 由 `ContextBundle` 一次性产出 |
| 44 | [大重构 Phase 3：Graph Nodes 拆分为薄适配器](./prompts/44-refactor-graph-nodes-thin-adapters.md) | ✅ | 2026-05-22 | `graph/nodes/` 按阶段拆分，facade 兼容旧导入与 monkeypatch 路径 |
| 45 | [大重构 Phase 4：RAG 模块边界与可替换检索服务](./prompts/45-refactor-rag-module-boundaries.md) | ✅ | 2026-05-22 | 拆出 RAG service、Qdrant store、BM25、rerank、formatting |
| 46 | [大重构 Phase 5：统一 LLM Gateway 与模型用途策略](./prompts/46-refactor-llm-gateway.md) | ✅ | 2026-05-22 | 新增 `ModelUseCase` 与 LLM Gateway，收敛 chat/embedding/rerank/model policy |
| 47 | [大重构 Phase 6：Observability 事件化与 LangSmith 适配](./prompts/47-refactor-observability-events.md) | ✅ | 2026-05-22 | 用 domain events 解耦业务逻辑与 LangSmith metadata |
| 48 | [大重构 Phase 7：代码地图与 README 最终对齐](./prompts/48-refactor-docs-maps-readme.md) | ✅ | 2026-05-22 | 新增 `docs/maps/` 6 份代码地图；README 收敛为当前运行入口；复核 AGENTS/README/progress 治理一致 |
| 49 | [控制面 Phase 0：Intent 契约与评测种子先行](./prompts/49-control-plane-intent-contracts-eval.md) | ✅ 完成 | 2026-05-22 | 新增 `IntentDecision` 契约与 intent eval seed；不改变运行路径 |
| 50 | [控制面 Phase 1：Signals 与确定性 Intent Engine](./prompts/50-control-plane-intent-signals-rules.md) | ✅ 完成 | 2026-05-22 | 新增 `intent/` signals、确定性规则与 `classify_intent()`；旧事实规则保持兼容 |
| 51 | [控制面 Phase 2：LLM Structured Classifier 与冲突校验](./prompts/51-control-plane-structured-classifier.md) | ✅ 完成 | 2026-05-22 | 新增 intent 小模型结构化分类器、LLM Gateway 用途与 conflict check |
| 52 | [控制面 Phase 3：Intent Engine 影子运行与观测接入](./prompts/52-control-plane-shadow-observability.md) | ✅ 完成 | 2026-05-22 | 新 intent 旁路运行并记录 metadata，不改变旧路径 |
| 53 | [控制面 Phase 4：Policy Gate 接管 fact_update fast path](./prompts/53-control-plane-policy-fast-path.md) | ✅ 完成 | 2026-05-24 | fast path 改由 policy 准入，第一人称疑问不再写记忆 |
| 54 | [控制面 Phase 5：memory_query 一等路径与记忆回答执行器](./prompts/54-control-plane-memory-query-executor.md) | ✅ 完成 | 2026-05-24 | 新增 `memory_query_executor`，基于 memory_profile / mem0 / thread 可靠记忆回答，缺失时诚实说明 |
| 55 | [控制面 Phase 6：Agent 级 Fallback Manager 与降级策略](./prompts/55-control-plane-agent-fallback-manager.md) | ✅ 完成 | 2026-05-24 | 新增 FallbackDecision / Fallback Manager，统一 intent、memory、RAG、tool、schema/LLM、output guard fallback metadata |
| 56 | [控制面 Phase 7：Intent Feedback 与控制面评测闭环](./prompts/56-control-plane-feedback-eval-loop.md) | ✅ 完成 | 2026-05-24 | 新增 feedback helper、本地 intent eval runner 与 intent seed LangSmith dry-run 同步 |
| 57 | [控制面 Phase 8：README、代码地图与文档治理最终对齐](./prompts/57-control-plane-docs-readme-maps-final.md) | ✅ 完成 | 2026-05-24 | README、docs/maps、PRD 落地偏差、progress 与文档治理最终对齐 |
| 58 | [意图权威收敛 Phase 0：行为冻结与双轨分歧审计](./prompts/58-intent-authority-behavior-freeze.md) | ✅ 完成 | 2026-05-25 | 新增 `test_intent_authority_characterization.py` 双轨分歧矩阵；5 条第一人称疑问目标 `memory_query`；运行路径不变 |
| 59 | [意图权威收敛 Phase 1：单一权威派生契约](./prompts/59-intent-authority-derived-turn-contract.md) | ✅ 完成 | 2026-05-25 | 新增 `turn_type_decision_from_intent()`；`test_intent_authority_contract.py` 覆盖全 route 映射与 reason；主图仍走旧 `classify_turn_type()` |
| 60 | [意图权威收敛 Phase 2：Graph 切换到 IntentDecision 单源](./prompts/60-intent-authority-graph-cutover.md) | ✅ 完成 | 2026-05-25 | `load_memory_node()` 仅 `classify_intent()` + 派生 `turn_type`；`intent_conflict` 常态为 false；分类失败时降级旧分类器 |
| 61 | [意图权威收敛 Phase 3：旧 turn_type 分类器降级与清理](./prompts/61-intent-authority-legacy-turn-type-cleanup.md) | ✅ 完成 | 2026-05-25 | `classify_turn_type()` 委托 intent authority；移除 `rag.intent` 独立分类依赖；`test_turn_type.py` 改为 adapter 对齐测试 |
| 62 | [意图权威收敛 Phase 4：README、代码地图与文档最终对齐](./prompts/62-intent-authority-docs-readme-maps-final.md) | ✅ 完成 | 2026-05-25 | README、docs/maps、PRD 落地状态同步单源 intent authority；progress 收口 58-62 |
| 63 | [结构化记忆写入 Phase 0：契约与评测种子](./prompts/63-structured-memory-contract-eval.md) | ✅ | 2026-05-25 | `StructuredMemoryRecord` 契约 + `memory_write_seed.json`；characterization 冻结 infer 路径 `stored_empty` 基线 |
| 64 | [结构化记忆写入 Phase 1：Slot Fill 抽取器](./prompts/64-structured-memory-slot-fill.md) | ✅ | 2026-05-25 | `memory/structured_record.py` slot fill + canonical 文本；覆盖 name/birthday/city/job/company.address/preference |
| 65 | [结构化记忆写入 Phase 2：Deterministic mem0 Store](./prompts/65-structured-memory-deterministic-store.md) | ✅ | 2026-05-25 | `store_structured_record` + `infer=False` canonical 写入；`memory_write.mode=structured` trace |
| 66 | [结构化记忆写入 Phase 3：Graph 接入与 post_turn 双轨路由](./prompts/66-structured-memory-graph-cutover.md) | ✅ | 2026-05-25 | `memory_write_record` ephemeral + load_memory slot fill + post_turn structured/inferred 互斥路由 |
| 67 | [结构化记忆写入 Phase 4：话术、可观测与 eval runner](./prompts/67-structured-memory-observability-eval.md) | ✅ | 2026-05-25 | Commit 话术含 record 摘要；path contract `memory_write.mode`/attribute；`run_memory_write_eval.py` + seed 5/5 pass |
| 68 | [结构化记忆写入 Phase 5：README、代码地图与文档最终对齐](./prompts/68-structured-memory-docs-final.md) | ✅ | 2026-05-25 | README/maps/PRD 双轨写入收口；issue 关联已落地方案；63-68 全部完成 |
| 69 | [LangMem 迁移 Phase 0：契约、行为冻结与依赖 Spike](./prompts/69-langmem-migration-contract-spike.md) | ✅ | 2026-05-25 | `contracts/memory_store.py`；characterization + spike 测试；`langmem>=0.0.30`；Store 来自 `langgraph-checkpoint-postgres`（同库 setup 已验证） |
| 70 | [LangMem 迁移 Phase 1：Store 工厂与用户记忆读路径](./prompts/70-langmem-store-read-path.md) | ✅ | 2026-05-25 | `memory/store.py` + `memory/read.py`；`fetch_user_memories` 默认走 Store；`MEMORY_STORE_*` settings |
| 71 | [LangMem 迁移 Phase 2：Structured Write 切 Store](./prompts/71-langmem-structured-write.md) | ✅ | 2026-05-25 | `memory/write.py` profile put；trace 增 `memory_store.*`；eval structured 5/5；inferred 仍 mem0 |
| 72 | [LangMem 迁移 Phase 3：Inferred Write 切 langmem](./prompts/72-langmem-inferred-write.md) | ✅ | 2026-05-25 | `langmem_manager` + `write.extract_and_store`；`MEMORY_EXTRACT`；post_turn 不再 mem0 infer |
| 73 | [LangMem 迁移 Phase 4：删除 mem0 与 Qdrant 用户记忆配置](./prompts/73-langmem-remove-mem0.md) | ✅ | 2026-05-25 | 移除 mem0ai/dead code；仅保留 MEMORY_* + Store/langmem；521 非 integration 测试绿 |
| 74 | [LangMem 迁移 Phase 5：README、命名收口与文档最终对齐](./prompts/74-langmem-docs-final.md) | ✅ | 2026-05-25 | `user_memories` 重命名；README/maps/PRD/issue/evals 收口；521 非 integration 测试绿 |
| 75 | [LangMem Store 前置：Postgres + pgvector 运维配置](./prompts/75-postgres-pgvector-store-setup.md) | ✅ | 2026-05-25 | README 同库运维章节；OrbStack `my-postgres` 已启用 pgvector 0.8.2；integration spike 全绿 |
| 76 | [memory_query 润色 Phase 0：行为冻结与评测种子](./prompts/76-memory-query-polish-behavior-freeze.md) | ✅ | 2026-05-26 | 冻结 `MemoryQueryResult`/graph 路径 characterization；新增 `memory_query_polish_seed.json` 8 条 |
| 77 | [memory_query 润色 Phase 1：契约、配置与小模型客户端](./prompts/77-memory-query-polish-contract-config.md) | ✅ | 2026-05-26 | `MEMORY_QUERY_POLISH_*` settings/env；`ModelUseCase.MEMORY_QUERY_POLISH`；`query_polish.py` 校验+fallback；14 用例 |
| 78 | [memory_query 润色 Phase 2：Graph 接入与 fallback](./prompts/78-memory-query-polish-graph-cutover.md) | ✅ | 2026-05-26 | `memory_query_reply -> memory_query_polish -> post_turn_jobs`；draft 与 final 分层；开关/回退/单条 assistant 测试 |
| 79 | [memory_query 润色 Phase 3：可观测、eval 与 trace 验证](./prompts/79-memory-query-polish-observability-eval.md) | ✅ | 2026-05-26 | `memory_query.polish.*` metadata/事件；`run_memory_query_polish_eval.py` seed 8/8；tracing/path 测试 |
| 80 | [memory_query 润色 Phase 4：README、代码地图与文档最终对齐](./prompts/80-memory-query-polish-docs-final.md) | ✅ | 2026-05-26 | README/maps/PRD/progress 同步 polish 当前事实；memory_query 润色 76-80 全部收口 |
| 81 | [演示平台：Back 数据库、迁移与种子](./prompts/81-demo-back-database-seed.md) | ✅ | 2026-05-26 | SQLAlchemy+Alembic；`common_agent_back` 六表；种子 role-* + admin/alice/bob + 3 学生；pytest SQLite fixture |
| 82 | [演示平台：Back Cookie Session 与认证 API](./prompts/82-demo-back-session-auth.md) | ✅ | 2026-05-26 | login/logout/me；signed cookie session；CORS 5173+credentials；`test_demo_auth.py` 8 用例 |
| 83 | [演示平台：Front Vue3 SPA 脚手架](./prompts/83-demo-front-vue-scaffold.md) | ⬜ | — | 可与 81–82 并行；Vite/TS/Pinia/Naive/proxy |
| 84 | [演示平台：Front 登录、布局、欢迎页与 Chat 空壳](./prompts/84-demo-front-auth-layout-home.md) | ⬜ | — | 依赖 82、83；FAB+Drawer 空壳 |
| 85 | [演示平台：学生 CRUD（Back + Front）](./prompts/85-demo-students-crud.md) | ⬜ | — | 依赖 81、82、84；**演示 MVP 里程碑** |
| 86 | [演示平台：账号管理（角色与用户 CRUD）](./prompts/86-demo-admin-accounts-crud.md) | ⬜ | — | 依赖 81、82、84 |
| 87 | [演示平台：Agent role_ids[] 与 RAG OR 检索](./prompts/87-demo-agent-role-ids-rag-or.md) | ⬜ | — | Agent 侧；可与 86 并行 |
| 88 | [演示平台：Back context 注入与 chat_threads](./prompts/88-demo-back-context-chat-threads.md) | ⬜ | — | 依赖 82、86、87 |
| 89 | [演示平台：Agent KB API + Back kb_document_meta 双写](./prompts/89-demo-kb-meta-agent-apis.md) | ⬜ | — | 依赖 81、86、87 |
| 90 | [演示平台：Front RAG 管理页](./prompts/90-demo-front-rag-admin-ui.md) | ⬜ | — | 依赖 89、84、86 |
| 91 | [演示平台：ChatDrawer SSE 与 history](./prompts/91-demo-front-chat-drawer-sse.md) | ⬜ | — | 依赖 88、84 |
| 92 | [演示平台：文档收口与 legacy Front 移除](./prompts/92-demo-docs-final-alignment.md) | ⬜ | — | 依赖 81–91；README、demo-walkthrough、maps |

---

## 变更日志

| 日期 | 说明 |
|------|------|
| 2026-05-19 | 初始化进度文档与 23 项任务卡 |
| 2026-05-19 | 文档：任务 01 固化 .env 契约（SiliconFlow LLM/Embedding/Rerank、LangSmith、Qdrant）；同步根 README 环境变量表、任务 02 字段列表 |
| 2026-05-19 | 完成任务 01：三目录 + uv/deepagents 骨架 + `.env.example` 契约 |
| 2026-05-19 | 完成任务 02：Pydantic Settings + `get_settings()` 单例与测试 |
| 2026-05-19 | 完成任务 03：Postgres Checkpointer 工厂、集成测试 thread 往返 |
| 2026-05-19 | 完成任务 04：ChatRequest/RequestContext/ToolSpec/ClientAction/ChatResponse Pydantic 模型 |
| 2026-05-19 | 完成任务 05：FastAPI Gateway `GET /health`、`POST /internal/chat` stub；`test_gateway_health.py` 3 用例 |
| 2026-05-19 | 完成任务 06：入站规则护栏 + Gateway 集成；`test_guardrails_inbound.py` 7 用例 |
| 2026-05-19 | 文档：任务 07/17、根 README 明确 mem0 仅本地 OSS+Qdrant，禁止托管云 |
| 2026-05-19 | 完成任务 07：本地 mem0 读取 + Qdrant 配置；`mem0ai`/`qdrant-client`；`test_mem0_read.py` 9 用例 |
| 2026-05-19 | 完成任务 08：checkpoint 历史读取 + rolling summary；`test_history.py` 10 用例（含 integration） |
| 2026-05-19 | 完成任务 09：mem0+短期 query rewrite、`rewrite_node`；`langchain-openai`；`test_rewrite.py` 9 用例 |
| 2026-05-19 | 完成任务 10：RAG 混合路由（规则+LLM）、`rag_skipped`；`test_rag_router.py` 16 用例 |
| 2026-05-19 | 完成任务 11：`retrieve` + `rag_retrieval_node`；dense/sparse(文本回退)+rerank；`QDRANT_MOCK` fixture |
| 2026-05-19 | 完成任务 12：`build_context` K+M+summary 组装；prefix/recent 去重；`test_context_assembly.py` 9 用例 |
| 2026-05-19 | 完成任务 13：Supervisor 主图（护栏→并行 mem0/history→rewrite→RAG→组装→deepagents）；`test_graph_*.py` 5 用例 |
| 2026-05-19 | 文档：新增任务 13.5（State/context_schema 拆分）及影响面清单；根 README 同步 State/Context 契约 |
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
| 2026-05-19 | 完成任务 23：`front/` 占位页；手动测试说明；Back 增加 Front CORS；**第一期完成** |
| 2026-05-20 | 文档：新增任务 **24** [mem0 All-in（infer=True）](./prompts/24-allin-mem0.md)；同步根 README、架构 PRD 记忆写入说明（目标态） |
| 2026-05-20 | 完成任务 24：mem0 `infer=True` 写入；移除应用层 `mem0_extract` 热路径 |
| 2026-05-20 | 文档：新增任务 **25** [State 精简 mem0_text](./prompts/25-state-mem0-text-cleanup.md)；根 README 同步目标态（仅 `mem0_memories`） |
| 2026-05-20 | 完成任务 25：AgentState 仅 `mem0_memories`；rewrite 节点内 `format_mem0_for_system` |
| 2026-05-20 | 文档：新增任务 **26** [Rewrite 条件跳过](./prompts/26-rewrite-conditional-skip.md)；根 README 同步条件 rewrite 与 LangSmith 说明 |
| 2026-05-20 | 文档：删除旧架构文档与 Agent 局部 README，根目录 README 作为唯一项目入口 |
| 2026-05-20 | 文档：新增根 `AGENTS.md` 作为跨工具 AI 规则源，`.cursor/skills` 改为 Cursor 适配层 |
| 2026-05-20 | 完成任务 26：`should_rewrite` 条件跳过 rewrite LLM；`REWRITE_SKIP_ENABLED`；LangSmith `rewrite_skipped` metadata |
| 2026-05-20 | 文档：新增任务 **27** [Rewrite / RAG Router 小模型与超时保护](./prompts/27-rewrite-router-small-model.md)，准备将小任务从 Kimi-K2.6 切到低延迟模型 |
| 2026-05-21 | 完成任务 27：rewrite/router 小模型配置、`max_completion_tokens`、timeout、fallback metadata 与 `.env.example`/本机 `.env` 同步 |
| 2026-05-21 | 修复任务 27 真实 trace 回归：rewrite 对「我出生于1997年」类个人事实陈述跳过 LLM；LLM 篡改数字时回退原文 |
| 2026-05-21 | 修复任务 27 router timeout 回归：`rag_router` 对「我公司在天翔街188号」类公司事实陈述直接 skip RAG；router timeout 默认 5 秒且小任务 LLM 禁用自动重试 |
| 2026-05-21 | 文档：基于运行时优化 PRD 新增任务 28-40，将 turn_type、路径契约、快速路径、deepagents 分层、流式与评测拆成小任务卡 |
| 2026-05-21 | 完成任务 28：新增 `turn_type` 分类层，写入单轮 state 与 LangSmith metadata；执行路径保持不变 |
| 2026-05-21 | 完成任务 29：新增 `path_metrics` 单轮路径契约，记录 rewrite/router/RAG/supervisor should/called、LLM 调用次数与 pass/fail metadata |
| 2026-05-21 | 完成任务 30：`fact_update` 走模板确认快速路径，跳过 rewrite/router/RAG/Supervisor，保留 checkpoint 与 post_turn mem0 调度观测 |
| 2026-05-21 | 完成任务 31：`chitchat` 走轻量执行器，默认模板回复，可选小模型；跳过 rewrite/RAG/deepagents，并补充 executor tracing 与路径契约测试 |
| 2026-05-21 | 完成任务 32：rewrite/router 接收 `turn_type`；`knowledge_query` 直进 RAG，`fact_update`/`chitchat`/`client_action` 跳过小模型，保留旧规则 fallback |
| 2026-05-21 | 完成任务 33：新增 executor router 与 `rag_answer_executor` / `action_executor` / `deepagents_executor` 分层；trace 记录 `executor` 与原因 |
| 2026-05-21 | 完成任务 34：新增 mem0 专用小模型配置；mem0 写入返回结构化 `status/reason/stored_count`，并补日志与 trace metadata |
| 2026-05-21 | 完成任务 35：新增 `memory_profile` 运行时归一化视图；system prompt 优先注入 profile，并保留未归类 mem0 自由文本 |
| 2026-05-21 | 文档规则：固化 Agent 环境契约三者同步要求（`config.py` / `.env.example` / `.env`），并以 `test_env_files_match_settings_contract` 自动校验 |
| 2026-05-21 | 完成任务 36：新增上下文预算配置；限制 memory_profile、mem0、summary、RAG、tools schema 与 model messages，并输出 `budget_truncated` 等 metadata |
| 2026-05-21 | 完成任务 37：Agent SSE 对无工具文本回合接入模型 streaming callback，Back 保持 SSE 透传，`client_actions` 继续走结构化 JSON |
| 2026-05-21 | 完成任务 38：流式输出增加增量出站检查与 `segment_id`，违规时发送 `retract` / `replace`；Front demo 支持撤回和替换已展示片段 |
| 2026-05-21 | 完成任务 39：新增 `agent/evals/seed.json` 与 `sync_langsmith_dataset.py`；将 `answer_score` / `path_score` 预期拆开，并补 seed smoke test |
| 2026-05-21 | 完成任务 40：RAG 检索增加本地 BM25 fallback，dense 失败仍可词法召回；补 RAG seed、检索评测脚本与 role_id 防越权测试 |
| 2026-05-21 | 文档：新增 [Agent 大重构 PRD](./prd/agent-major-refactor.md)，目标是契约优先、薄图编排、显式状态生命周期、ContextBundle、RAG 模块化、LLM Gateway 与 observability 事件化 |
| 2026-05-21 | 文档：基于大重构 PRD 新增任务 41-48，将行为冻结、契约层、ContextBundle、Graph nodes 拆分、RAG 模块化、LLM Gateway、observability 事件化和代码地图拆成可执行任务卡 |
| 2026-05-21 | 文档治理：在根 `AGENTS.md` 与 README 固化文档层级和更新机制；PRD 不覆盖 README 当前契约，`docs/maps/` 等重构后生成；其它 AI 若要改进此秩序需先说明原因并取得用户同意 |
| 2026-05-21 | 完成任务 41：`make test` 改跑当前 `tests/` 非 integration 集；新增 state lifecycle、典型 path、SSE event contract 与验证入口测试，冻结重构前行为 |
| 2026-05-21 | 完成任务 42：新增 `contracts/` 契约层与 typed models；`graph`/`rag`/`memory` 保持兼容导出，SSE formatter 增加契约校验 |
| 2026-05-22 | 完成任务 43：新增 `ContextBundle` / `ContextSources`，`context_assembly` 一次性产出模型上下文，supervisor/executor 消费同一 bundle 与 budget metadata |
| 2026-05-22 | 完成任务 44：将 `graph/nodes.py` 拆为 `graph/nodes/` 阶段模块，保留 `graph.nodes` facade、图拓扑与既有导入路径兼容 |
| 2026-05-22 | 完成任务 45：RAG 检索拆为 `domain.rag` service/merge/BM25/formatting、`infrastructure.qdrant` KB store/payload parser 与 `infrastructure.llm` rerank client，`rag.retriever` 保持兼容 facade |
| 2026-05-22 | 完成任务 46：新增 `contracts.llm.ModelUseCase` 与 `infrastructure.llm.LlmGateway`；rewrite/router/chitchat/supervisor/summary/embedding/rerank/mem0 模型策略统一入口 |
| 2026-05-22 | 完成任务 47：新增 typed observability events、per-context event collector 与 LangSmith metadata mapper；关键路径改为 emit event，保留 `attach_run_metadata()` 兼容 facade |
| 2026-05-22 | 完成任务 48：新增 `docs/maps/` 六份代码地图；README 改为当前运行入口与验证入口；复核 `AGENTS.md`、README、`docs/progress.md` 的文档治理一致性 |
| 2026-05-22 | 文档：新增 [Agent 控制面、意图治理与兜底 PRD](./prd/agent-control-plane-intent-fallback.md)，沉淀意图识别、Policy Gate、memory_query、Agent 级 fallback 与 feedback 闭环方案 |
| 2026-05-22 | 文档：基于控制面 PRD 新增任务 **49-57**，按契约与 eval、signals/rules、structured classifier、shadow observability、Policy Gate、memory_query、Fallback Manager、feedback eval、文档最终对齐拆分执行 |
| 2026-05-22 | 完成任务 49：新增 `contracts.intent.IntentDecision` / `IntentFeedback`、`memory_query` / `safety_refusal` route 契约、`intent_seed.json` 与 seed/contract 测试；运行路径保持不变 |
| 2026-05-22 | 完成任务 50：新增 `intent` 包，抽取 signals、高置信确定性规则与纯逻辑 `classify_intent()`；第一人称疑问进入 `memory_query`，运行 graph 未接入新控制面 |
| 2026-05-22 | 完成任务 51：新增 `ModelUseCase.INTENT_CLASSIFIER`、结构化 intent classifier、冲突检测与 schema/timeout/provider fallback；运行 graph 未接入新控制面 |
| 2026-05-22 | 完成任务 52：主图在旧 `turn_type` 分类旁影子运行 `classify_intent()`，新增 intent state、事件和 LangSmith metadata；旧路径与用户可见行为保持不变 |
| 2026-05-24 | 完成任务 53：新增 Policy Gate 接管 `fact_update` fast path 准入；被拒绝的旧事实路径不模板确认、不调度 mem0 写入，第一人称疑问进入保守路径 |
| 2026-05-24 | 完成任务 54：新增 `memory_query` 一等 graph 路由与 `memory_query_executor`；「我是谁」类问题跳过 rewrite/RAG/deepagents，不调度 mem0 写入，按可靠记忆回答或诚实缺失 |
| 2026-05-24 | 完成任务 55：新增 Agent 级 fallback 契约、策略矩阵与 `fallback.*` 观测字段；RAG 空/弱命中不再交给 deepagents 兜底，memory missing/tool unavailable/output guard 等场景统一记录 |
| 2026-05-24 | 完成任务 56：新增 Intent feedback 标准 failure_type、feedback→seed helper、本地 intent/path eval runner；`intent_seed.json` 纳入第一人称疑问误判回归样本，LangSmith 同步脚本支持 intent seed dry-run |
| 2026-05-24 | 完成任务 57：README 同步控制面当前契约；docs/maps 增补 intent、policy、memory_query、fallback、feedback/eval 入口并新增 control-plane 地图；控制面 PRD 补充落地状态与偏差说明；文档治理顺序保持 AGENTS.md 约定 |
| 2026-05-25 | 文档：新增 [Agent 意图权威来源收敛 PRD](./prd/agent-intent-authority-consolidation.md)，并拆分任务 **58-62**，目标是将旧 `turn_type` 与新 `IntentDecision` 双轨分类收敛为单一权威来源，最后统一更新 README/maps/progress |
| 2026-05-25 | 完成任务 58：新增 `test_intent_authority_characterization.py` 冻结旧 `classify_turn_type()` 与新 `classify_intent()` 双轨分歧；11 条典型样例中 5 条第一人称疑问分歧目标为 `memory_query`，6 条一致样例无分歧；运行代码未改 |
| 2026-05-25 | 完成任务 59：新增 `intent.engine.turn_type_decision_from_intent()` 派生契约；仅读取 `IntentDecision.turn_type` / `turn_type_reason`；`test_intent_authority_contract.py` 覆盖 8 条 `IntentRoute` 映射；主图运行路径不变 |
| 2026-05-25 | 完成任务 60：主图 `load_memory_node()` 切换为 `classify_intent()` 单源并派生 `turn_type`；第一人称疑问不再因旧分类进入 fact_update；`intent_conflict` 常态 false；分类失败时降级 `classify_turn_type()` |
| 2026-05-25 | 完成任务 61：`graph.turn_type.classify_turn_type()` 降级为 intent authority 兼容 adapter；移除对 `rag.intent` 全局启发式的直接依赖；characterization/turn_type 测试改为单源对齐；分类失败保守回退 `general_chat` |
| 2026-05-25 | 完成任务 62：README、docs/maps、PRD 同步 `IntentDecision` 单源权威与 `turn_type` 兼容派生当前事实；意图权威收敛任务 58-62 全部完成 |
| 2026-05-25 | 文档：新增 [Agent 结构化记忆写入 PRD](./prd/agent-structured-memory-write.md)（Single Extraction Point）；拆分任务 **63-68**，目标为 fact_update 结构化 slot fill + infer=False 落库，保留 general_chat infer 慢路径 |
| 2026-05-25 | 完成任务 63：新增 `contracts.memory_write`（`StructuredMemoryRecord` / `MemoryWriteMode`）、`memory_write_seed.json` 与 seed/contract/characterization 测试；冻结 fact_update + infer 路径 `stored_empty` 基线；运行路径不变 |
| 2026-05-25 | 完成任务 64：新增 `memory/structured_record.py`（`build_structured_memory_record` + `canonical_fact_text`）；纯规则 slot fill，birthday 归一为四位年份；无 LLM、无 mem0/graph 接入 |
| 2026-05-25 | 完成任务 65：新增 `store_structured_record`（`infer=False` + canonical fact + metadata）；`MEM0_MOCK` 返回可预测 stored；seed 正例 mock 下 `stored_count>=1`；`extract_and_store` 行为无回归 |
| 2026-05-25 | 完成任务 66：graph 接入 structured write；`load_memory` slot fill 写入 `memory_write_record`；post_turn 双轨路由；path metrics 记录 `memory_write_mode`；policy denied / memory_query 仍 skip mem0 |
| 2026-05-25 | 完成任务 67：`fact_update_confirm` 话术含 record 摘要（`已记住：{label}={value}`）；path contract 区分 structured/inferred 与 attribute；新增 `run_memory_write_eval.py`；seed 5/5 pass；`stored_empty` regression 被 eval 捕获 |
| 2026-05-25 | 完成任务 68：README/maps/PRD 同步 structured vs inferred 双轨写入；`agent-structured-memory-write.md` 落地状态与偏差；issue 关联方案；结构化记忆写入 63-68 全部收口 |
| 2026-05-25 | 完成任务 71：`memory/write.py` structured profile `store.put`；post_turn 不再 mem0 add；`ExtractionMethod.STORE_PROFILE`；eval seed 5/5 pass |
| 2026-05-25 | 完成任务 70：`memory/store.py` 池化 PostgresStore（pgvector index=EMBEDDING_MODEL_DIMS）；`memory/read.py` profile+collection 读；`load_memory` 传 user message 作 search query；env 新增 `MEMORY_STORE_*` |
| 2026-05-25 | 完成任务 75：README 增加 Postgres+pgvector 同库运维（OrbStack/Docker 双路径）；本机 `common_agent` 启用 `vector` 0.8.2；checkpointer + Store semantic index integration 全绿 |
| 2026-05-25 | 完成任务 69：`contracts/memory_store.py`（namespace/profile/read 契约）；`test_langmem_migration_characterization.py` 冻结 mem0 基线；`test_langmem_store_spike.py` 验证 Store+checkpointer 同库；pin `langmem>=0.0.30`；Store 实现随 `langgraph-checkpoint-postgres>=3.1.0`，无需单独 store 包 |
| 2026-05-25 | 完成任务 73：删除 mem0ai、`mem0_client`/`mem0_write`、QDRANT_COLLECTION_MEM0 与 MEM0_* settings；`MEMORY_FREE_TEXT_MAX_FACTS`；AGENTS.md 改为 Store/langmem 约束 |
| 2026-05-25 | 完成任务 74：`mem0_memories` → `user_memories`；README/maps/PRD/issue/evals 同步 Store+langmem 当前事实；LangMem 迁移 69-75 全部收口 |
| 2026-05-26 | memory_query 润色 prompt：LLM 输入移除 `draft_reply`（仅作 fallback），改由 question + evidence 生成自然话术，避免小模型照抄模板 |
| 2026-05-26 | 运行契约：`MEMORY_QUERY_POLISH_USE_LLM` 默认改为 `true`；`.env.example` 同步小模型名；graph  characterization 测试显式 `false` 以隔离 deterministic 断言 |
| 2026-05-26 | 完成任务 80：README、docs/maps、PRD 同步 memory_query 润色当前运行事实（`memory_query_polish` 节点、`MEMORY_QUERY_POLISH_*`、eval runner）；progress 80/80 完成 |
| 2026-05-26 | 完成任务 79：新增 `memory_query.polished` 事件与 `memory_query.polish.*` path/trace metadata；`run_memory_query_polish_eval.py` 本地 seed 8/8；篡改/缺失/回退 eval 与 tracing 测试 |
| 2026-05-26 | 完成任务 78：主图接入 `memory_query_polish` 节点；`memory_query_reply` 写 draft/result，polish 追加唯一 assistant message；默认关闭时行为不变；mock 成功/校验失败回退测试 |
| 2026-05-26 | 完成任务 77：新增 `contracts/memory_query_polish`、`ModelUseCase.MEMORY_QUERY_POLISH`、`MEMORY_QUERY_POLISH_*` env 契约、`memory/query_polish.py` 小模型润色与输出校验 fallback；`test_memory_query_polish.py` 14 用例；未接 graph |
| 2026-05-26 | 完成任务 76：补充 memory_query characterization/path contract 测试；新增 `memory_query_polish_seed.json`（姓名/地址/偏好/缺失/thread fallback/禁止篡改）与 seed smoke test；运行行为不变 |
| 2026-05-26 | 文档：新增 [Agent memory_query 小模型话术润色 PRD](./prd/agent-memory-query-polish.md)，并拆分任务 **76-80**；最后任务负责 README、docs/maps、PRD 与 progress 最终对齐 |
| 2026-05-26 | 完成任务 82：Back HttpOnly Cookie Session（`SessionMiddleware`+signed cookie）；`POST /api/auth/login|logout`、`GET /api/me`；bcrypt 校验；PRD 统一错误体；`SESSION_SECRET`/`CORS_ORIGINS` env；`test_demo_auth.py` 8 用例 |
| 2026-05-26 | 完成任务 81：Back `db/` ORM（roles/users/user_roles/students/kb_document_meta/chat_threads）、Alembic 初始迁移、`db.seed` CLI、`domain/role_id` 格式校验；`DATABASE_URL`/`ADMIN_SEED_PASSWORD` env 契约；`test_demo_database.py` 4 用例（SQLite fixture） |
| 2026-05-26 | 文档：基于 [演示平台 PRD](./prd/demo-admin-console.md) 拆分任务 **81-92**（12 张任务卡）；**92** 负责 README、`role_ids[]` 契约、demo-walkthrough、maps、移除 legacy static front 与 progress 收口 |
