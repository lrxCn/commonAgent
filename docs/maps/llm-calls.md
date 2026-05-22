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
- `MEM0_WRITE`：mem0 `infer=True` 写入。
- `SUMMARY`：rolling summary 更新。
- `EMBEDDING`：query/doc embedding。
- `RERANK`：候选 rerank。

## 调用路径

- Supervisor：[supervisor.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/graph/supervisor.py:1)
- Rewrite：[rewrite.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/rag/rewrite.py:1)
- Router：[router.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/rag/router.py:1)
- Chitchat：[chitchat_executor.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/graph/chitchat_executor.py:1)
- mem0 / summary：[mem0_write.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/memory/mem0_write.py:1)、[summary_job.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/memory/summary_job.py:1)
- Embedding / rerank：[service.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/domain/rag/service.py:1)

## 降级规则

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
