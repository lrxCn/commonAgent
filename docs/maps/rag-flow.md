# RAG Flow

回答的问题：一次知识检索从 route 到 retrieve、merge、rerank、formatting、权限过滤是怎样落地的。

## 路由

- 用户问题先经过 [turn_type.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/graph/turn_type.py:1) 分类。
- RAG 路由兼容入口在 [router.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/rag/router.py:1)。
- `knowledge_query` 直接检索；`fact_update`、`chitchat`、纯 `client_action` 跳过 RAG；不确定时再走规则或小模型。

## 检索

- 兼容 facade：[retriever.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/rag/retriever.py:1)
- 主服务：[service.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/domain/rag/service.py:1)
- Store：[kb_store.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/infrastructure/qdrant/kb_store.py:1)

步骤：

1. 用 LLM Gateway 生成 query embedding。
2. Qdrant dense search 按 `role_id` 过滤。
3. 本地 lexical/BM25 fallback 对同一 `role_id` 候选做词法召回。
4. 在 [merge.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/domain/rag/merge.py:1) 合并 dense + sparse 候选。
5. 用 rerank provider 重排。
6. 在 [formatting.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/domain/rag/formatting.py:1) 组装带 citation 的 RAG chunks。

## 权限与二查

- Qdrant 搜索阶段就按 `role_id` 过滤。
- payload 解析与 chunk 组装阶段仍保留 `role_id` 相关校验，避免越权 payload 混入。
- RagSubAgent 在 [rag_subagent.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/graph/rag_subagent.py:1)；只在主检索为空或弱命中时做第二次检索。

## Ingest

- Ingest 入口在 [ingest.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/rag/ingest.py:1) 与 [schemas_ingest.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/gateway/schemas_ingest.py:1)。
- 以 `doc_id + version` 写入，并按 `doc_name` 删除旧版本。

## 实现入口

- Route：[router.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/rag/router.py:1)
- Retrieve：[service.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/domain/rag/service.py:1)
- Store：[kb_store.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/infrastructure/qdrant/kb_store.py:1)
- Domain helpers：[merge.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/domain/rag/merge.py:1)、[bm25.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/domain/rag/lexical/bm25.py:1)、[formatting.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/domain/rag/formatting.py:1)

## 测试入口

- 路由逻辑：[test_rag_router.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_rag_router.py:1)
- 检索与 chunk 格式：[test_rag_retrieval.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_rag_retrieval.py:1)
- 边界与 fallback：[test_rag_boundaries.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_rag_boundaries.py:1)
- RagSubAgent：[test_rag_subagent.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_rag_subagent.py:1)
- Ingest API：[test_kb_ingest.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_kb_ingest.py:1)
