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

- rewrite 小模型失败：回退原文。
- router 小模型失败：保守走 RAG。
- embedding 失败：继续 lexical BM25 fallback。
- rerank API 失败：保持候选顺序的稳定 fallback 分数。
- Qdrant 空结果：允许主链路继续，只是 `rag_chunks` 为空；必要时 RagSubAgent 二查。

## 记忆与异步任务失败

- mem0 读取失败或 mock：返回空记忆，不阻断回合。
- post_turn summary / mem0 写入失败：只记日志和 observability metadata，不阻断当前响应。

## 观测失败

- 业务逻辑 emit event 后，subscriber 异常会被吞掉，不能影响业务路径。
- LangSmith metadata attach 失败不应改变最终回答。

## 实现入口

- 入站护栏：[inbound.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/guardrails/inbound.py:1)
- 出站护栏：[outbound.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/guardrails/outbound.py:1)
- SSE 错误处理：[chat.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/gateway/chat.py:1)
- RAG 降级：[service.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/domain/rag/service.py:1)
- LLM Gateway fallback：[gateway.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/infrastructure/llm/gateway.py:1)
- event collector：[events.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/observability/events.py:1)

## 测试入口

- 入站护栏：[test_guardrails_inbound.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_guardrails_inbound.py:1)
- 出站护栏与流式撤回：[test_guardrails_outbound.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_guardrails_outbound.py:1)、[test_chat_sse.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_chat_sse.py:1)
- RAG fallback：[test_rag_boundaries.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_rag_boundaries.py:1)
- rewrite/router fallback：[test_rewrite.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_rewrite.py:1)、[test_rag_router.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_rag_router.py:1)
- post_turn 非阻塞：[test_post_turn_graph.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_post_turn_graph.py:1)
- LangSmith / event 兼容：[test_tracing.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_tracing.py:1)
