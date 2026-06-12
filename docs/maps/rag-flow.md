# RAG Flow

回答的问题：一次知识检索从 route 到 retrieve、merge、rerank、formatting、权限过滤是怎样落地的。

## 路由

- `load_memory` 调用 `classify_intent()` 生成 `IntentDecision`，并派生兼容 `turn_type`；RAG router 读取 state 中的派生 `turn_type`，不是独立全局分类。
- [graph/turn_type.py](/Users/chenkexin/commonAgent/agent/src/graph/turn_type.py:1) 仅为兼容 adapter，内部委托 [engine.py](/Users/chenkexin/commonAgent/agent/src/intent/engine.py:1)。
- [policy.py](/Users/chenkexin/commonAgent/agent/src/intent/policy.py:1) 决定 `fact_update` 是否允许进入快速路径；被拒绝时 rewrite/router 会按保守路径处理。
- RAG 路由兼容入口在 [router.py](/Users/chenkexin/commonAgent/agent/src/rag/router.py:1)。
- `knowledge_query` 直接检索；Policy 通过的 `fact_update`、`memory_query`、`chitchat`、纯 `client_action` 跳过 RAG；不确定时再走规则或小模型。
- [rag/intent.py](/Users/chenkexin/commonAgent/agent/src/rag/intent.py:1) 只保留 rewrite/router 局部启发式兼容，不是全局意图来源。

## 检索

- 兼容 facade：[retriever.py](/Users/chenkexin/commonAgent/agent/src/rag/retriever.py:1)
- 主服务：[service.py](/Users/chenkexin/commonAgent/agent/src/domain/rag/service.py:1)
- Store：[kb_store.py](/Users/chenkexin/commonAgent/agent/src/infrastructure/qdrant/kb_store.py:1)

步骤：

1. 用 LLM Gateway 生成 query embedding。
2. Qdrant dense search 经 `roles_filter(context.role_ids[])`：payload `role_ids` 与用户集合 **MatchAny 交集**；迁移期 **M1 双读** 仍匹配仅含 legacy `role_id` 的 point（见 [kb_store.py](/Users/chenkexin/commonAgent/agent/src/infrastructure/qdrant/kb_store.py:1)）。
3. 本地 lexical/BM25 fallback 对同一 filter 候选做词法召回。
4. 在 [merge.py](/Users/chenkexin/commonAgent/agent/src/domain/rag/merge.py:1) 合并 dense + sparse 候选。
5. 用 rerank provider 重排。
6. 在 [formatting.py](/Users/chenkexin/commonAgent/agent/src/domain/rag/formatting.py:1) 组装带 citation 的 RAG chunks。

## 权限与二查

- **文档可见性**：payload `role_ids[]` 与用户 `context.role_ids[]` 须 **有交集**（ingest 在 [ingest.py](/Users/chenkexin/commonAgent/agent/src/rag/ingest.py:1) 写入完整数组；新 point 另写 `role_id=role_ids[0]` 供 M1 fallback）。
- [payload.py](/Users/chenkexin/commonAgent/agent/src/infrastructure/qdrant/payload.py:1) 在候选组装后再次按 `role_ids` 集合做交集过滤，防止越权 chunk 混入。
- 演示平台：Back Session 注入用户绑定的全部 `role_ids[]`；用户多角色时可见「任一角色的文档 ∪ 多角色文档中有交集者」。
- RagSubAgent 在 [rag_subagent.py](/Users/chenkexin/commonAgent/agent/src/graph/rag_subagent.py:1)；只在主检索为空或弱命中时做第二次检索。
- 二查后仍为空或弱命中会记录 RAG fallback；`knowledge_query` 最终返回无可靠来源模板，不让 deepagents 伪造来源。

## Ingest

- Ingest 入口在 [ingest.py](/Users/chenkexin/commonAgent/agent/src/rag/ingest.py:1) 与 [schemas_ingest.py](/Users/chenkexin/commonAgent/agent/src/gateway/schemas_ingest.py:1)。
- 请求体 `role_ids[]`（≥1）；同一 `doc_id` 只 ingest 一次，每个 point 携带相同 `role_ids[]`。
- 以 `doc_id + version` 写入，并按 `doc_name` 删除旧 version points（与角色无关）。
- Back admin：`kb_document_meta` + `kb_document_roles` 双写；PATCH 改角色或正文均 re-ingest（[kb.py](/Users/chenkexin/commonAgent/back/src/admin/kb.py:1)）。

## 实现入口

- Route：[router.py](/Users/chenkexin/commonAgent/agent/src/rag/router.py:1)
- Control plane：[engine.py](/Users/chenkexin/commonAgent/agent/src/intent/engine.py:1)、[policy.py](/Users/chenkexin/commonAgent/agent/src/intent/policy.py:1)
- Retrieve：[service.py](/Users/chenkexin/commonAgent/agent/src/domain/rag/service.py:1)
- Store：[kb_store.py](/Users/chenkexin/commonAgent/agent/src/infrastructure/qdrant/kb_store.py:1)
- Domain helpers：[merge.py](/Users/chenkexin/commonAgent/agent/src/domain/rag/merge.py:1)、[bm25.py](/Users/chenkexin/commonAgent/agent/src/domain/rag/lexical/bm25.py:1)、[formatting.py](/Users/chenkexin/commonAgent/agent/src/domain/rag/formatting.py:1)

## 测试入口

- 路由逻辑：[test_rag_router.py](/Users/chenkexin/commonAgent/agent/tests/test_rag_router.py:1)
- 检索与 chunk 格式：[test_rag_retrieval.py](/Users/chenkexin/commonAgent/agent/tests/test_rag_retrieval.py:1)
- 边界与 fallback：[test_rag_boundaries.py](/Users/chenkexin/commonAgent/agent/tests/test_rag_boundaries.py:1)
- 多角色 OR / 单角色隔离：[test_role_ids_filter.py](/Users/chenkexin/commonAgent/agent/tests/test_role_ids_filter.py:1)
- RagSubAgent：[test_rag_subagent.py](/Users/chenkexin/commonAgent/agent/tests/test_rag_subagent.py:1)
- 控制面路径：[test_policy_gate.py](/Users/chenkexin/commonAgent/agent/tests/test_policy_gate.py:1)、[test_intent_rules.py](/Users/chenkexin/commonAgent/agent/tests/test_intent_rules.py:1)、[test_intent_authority_characterization.py](/Users/chenkexin/commonAgent/agent/tests/test_intent_authority_characterization.py:1)
- Ingest API：[test_kb_ingest.py](/Users/chenkexin/commonAgent/agent/tests/test_kb_ingest.py:1)
