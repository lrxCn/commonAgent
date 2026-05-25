# LLM Calls

回答的问题：当前有哪些模型用途、从哪里选模型、失败时如何降级。

## 统一入口

- typed 用途定义在 [contracts/llm.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/contracts/llm.py:1)。
- provider 构造与调用边界在 [gateway.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/infrastructure/llm/gateway.py:1)。
- 策略解析在 [policy.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/infrastructure/llm/policy.py:1)。

## ModelUseCase

- `MAIN_ANSWER`：deepagents Supervisor 主回复。
- `RAG_ANSWER`：轻量知识问答执行器。
- `REWRITE`：指代消解。
- `ROUTER`：RAG 路由分类。
- `CHITCHAT`：寒暄回复。
- `MEMORY_EXTRACT`：langmem inferred 慢路径写入。
- `INTENT_CLASSIFIER`：低置信或冲突 intent 的结构化候选分类器。
- `SUMMARY`：rolling summary 更新。
- `EMBEDDING`：query/doc embedding。
- `RERANK`：候选 rerank。

## 调用路径

- Supervisor：[supervisor.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/graph/supervisor.py:1)
- Rewrite：[rewrite.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/rag/rewrite.py:1)
- Router：[router.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/rag/router.py:1)
- Chitchat：[chitchat_executor.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/graph/chitchat_executor.py:1)
- Intent classifier：[classifier.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/intent/classifier.py:1)
- 用户记忆 / summary：[write.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/memory/write.py:1)、[langmem_manager.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/memory/langmem_manager.py:1)、[summary_job.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/memory/summary_job.py:1)
- Embedding / rerank：[service.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/domain/rag/service.py:1)

## 降级规则

- 当前 graph 热路径的 `classify_intent()` 是确定性规则，不调用 `INTENT_CLASSIFIER`。
- `INTENT_CLASSIFIER` 输出必须通过 `IntentDecision` schema 校验；schema invalid 会尝试 repair，冲突时回退到规则/保守候选。
- rewrite/router 小模型只在必要时调用，超时或异常时回退保守路径。
- rerank HTTP 失败时按原候选顺序生成稳定 fallback 分数。
- embedding 失败时 RAG 继续走 lexical BM25 fallback。
- chitchat 小模型异常时回退模板回复。

## 实现入口

- 模型契约：[contracts/llm.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/contracts/llm.py:1)
- LLM Gateway：[gateway.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/infrastructure/llm/gateway.py:1)
- Provider client：[clients.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/infrastructure/llm/clients.py:1)

## 测试入口

- Gateway 策略与 streaming：[test_llm_gateway.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_llm_gateway.py:1)
- Supervisor 用途选择：[test_supervisor.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_supervisor.py:1)
- Rewrite / router fallback：[test_rewrite.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_rewrite.py:1)、[test_rag_router.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_rag_router.py:1)
- Chitchat fallback：[test_chitchat_executor.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_chitchat_executor.py:1)
- Intent classifier fallback：[test_intent_classifier.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_intent_classifier.py:1)
