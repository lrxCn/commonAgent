# Failure Modes

回答的问题：关键依赖失败时，系统如何降级，哪些错误会阻断回合，哪些不会。

## 会直接阻断当前回合的情况

- 入站护栏命中：在 [inbound.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/guardrails/inbound.py:1) 拦截，请求返回 400。
- Agent 不可达：Back 在 [forward.py](/Users/liurixing/Documents/codes/ai/commonAgent/back/src/services/forward.py:1) 返回 502。
- Graph 运行异常：Gateway SSE 输出 `error` 事件。

## 文本输出阶段的降级

- 出站护栏整段违规：返回安全替换文本。
- live streaming 增量违规：先发 `retract`，再发 `replace`。
- 最终自然语言为空：Gateway 退回 `supervisor_draft` 或护栏消息。

## RAG 与模型依赖失败

- intent 低置信或 `classify_intent()` 失败：记录 intent fallback，禁用危险快速路径，转入保守执行路径；`intent_conflict` 不再表示双轨分歧。
- Policy Gate 拒绝 `fact_update`：记录 policy denied fallback，不执行模板确认，不调度记忆写入。
- rewrite 小模型失败：回退原文。
- router 小模型失败：保守走 RAG。
- embedding 失败：继续 lexical BM25 fallback。
- rerank API 失败：保持候选顺序的稳定 fallback 分数。
- Qdrant 空结果或弱命中：先 RagSubAgent 二查；二查后仍无可靠来源时返回无来源模板，不交给 deepagents 猜测。

## 记忆与异步任务失败

- Store 读取失败或 mock：返回空记忆，不阻断回合。
- `memory_query` 没有可靠证据：返回诚实缺失回复，并记录 memory fallback。
- memory_query polish 小模型输出校验失败或调用异常：回退 deterministic draft，记录 `memory_query.polish.fallback_reason` 与 `memory_query.polish.validation_failed`；用户仍看到安全草稿回复。
- Policy 通过但 slot fill 失败（`structured_fill_failed`）：拒绝 fact_update 快路径，不输出 Commit 话术，不写入 structured record。
- post_turn structured 路径出现 `stored_empty`：视为缺陷；`memory_write_seed.json` 的 `regression_store_empty` 类别与 eval runner 用于捕获该回归。
- post_turn summary / 记忆写入失败：只记日志和 observability metadata，不阻断当前响应；structured 路径主图已基于 record 给出 Commit，异步 write 失败需靠 trace 告警（Front pending UI 未实现）。

## 工具与结构化输出失败

- 客户端工具不可用、未授权或参数不可构造：返回用户可见的 tool fallback，不执行工具。
- 模型输出的 `client_actions` schema 无效：记录 schema/tool fallback，并返回安全错误文本。
- 带 `tools[]` 的回合不做 live token streaming，避免结构化 JSON 被拆分。

## 观测失败

- 业务逻辑 emit event 后，subscriber 异常会被吞掉，不能影响业务路径。
- LangSmith metadata attach 失败不应改变最终回答。

## 实现入口

- 入站护栏：[inbound.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/guardrails/inbound.py:1)
- 出站护栏：[outbound.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/guardrails/outbound.py:1)
- SSE 错误处理：[chat.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/gateway/chat.py:1)
- RAG 降级：[service.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/domain/rag/service.py:1)
- LLM Gateway fallback：[gateway.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/infrastructure/llm/gateway.py:1)
- 记忆写入：[write.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/memory/write.py)
- 双轨 post_turn：[post_turn.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/memory/post_turn.py)
- Fallback manager：[fallback.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/intent/fallback.py:1)
- Fallback metrics：[path_contract.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/observability/path_contract.py:1)
- event collector：[events.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/observability/events.py:1)

## 测试入口

- 入站护栏：[test_guardrails_inbound.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_guardrails_inbound.py:1)
- 出站护栏与流式撤回：[test_guardrails_outbound.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_guardrails_outbound.py:1)、[test_chat_sse.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_chat_sse.py:1)
- RAG fallback：[test_rag_boundaries.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_rag_boundaries.py:1)
- rewrite/router fallback：[test_rewrite.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_rewrite.py:1)、[test_rag_router.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_rag_router.py:1)
- Fallback manager：[test_fallback_manager.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_fallback_manager.py:1)
- memory_query 缺失证据 / polish 回退：[test_memory_query_executor.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_memory_query_executor.py:1)、[test_memory_query_polish.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_memory_query_polish.py:1)
- post_turn 非阻塞：[test_post_turn_graph.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_post_turn_graph.py:1)
- structured write / stored_empty 回归：[test_memory_write_eval_runner.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_memory_write_eval_runner.py:1)、[test_structured_memory_characterization.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_structured_memory_characterization.py:1)
- fact_update slot fill 失败：[test_fact_update_fast_path.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_fact_update_fast_path.py:1)
- intent 分类失败 / 单源接入：[test_intent_shadow_graph.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_intent_shadow_graph.py:1)
- LangSmith / event 兼容：[test_tracing.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_tracing.py:1)
