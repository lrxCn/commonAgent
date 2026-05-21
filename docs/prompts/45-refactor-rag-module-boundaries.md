# 45 - 大重构 Phase 4：RAG 模块边界与可替换检索服务

## 建议执行模型

- 模型：GPT-5.5
- Reasoning：high
- 原因：RAG 是质量和权限风险最高的路径之一，重构必须保证 role_id 过滤、dense fallback、BM25、rerank 和评测行为不漂移。

## 依赖

44

## 背景

当前 `agent/src/rag/retriever.py` 同时负责 Qdrant client、payload 解析、dense search、text search、BM25、merge、rerank、mock、metadata 和 graph node adapter。文件过大，不利于后续替换 sparse、reranker、Qdrant collection 或权限策略。

本任务在保持外部 API 兼容的前提下拆分 RAG 内部边界。

## 目标

- 将 RAG 纯逻辑、Qdrant adapter、rerank client、格式化拆开。
- 保持 `rag.retriever.retrieve()` 和 `rag_retrieval_node()` 兼容。
- 让 dense、lexical/BM25、merge、rerank 可单独测试。
- 保持 role_id 权限过滤测试和评测 seed 有效。

## 范围

| 模块 | 变更 |
|------|------|
| `agent/src/contracts/rag.py` | 完善 `RagChunk`、`RagResult`、channel metadata |
| `agent/src/domain/rag/` | 新增 query plan、merge、formatting、service |
| `agent/src/domain/rag/lexical/` | tokenizer、BM25 scorer |
| `agent/src/infrastructure/qdrant/` | KB store、payload parser、dense/text/scroll adapter |
| `agent/src/infrastructure/llm/rerank_client.py` | 如 LLM Gateway 尚未完成，先建立 rerank adapter 占位 |
| `agent/src/rag/retriever.py` | 保留兼容 facade，调用新 service |
| `agent/src/rag/ingest.py` | 如需要，复用 Qdrant payload/collection helper |
| `agent/tests/` | 拆分/新增 RAG 单测与权限测试 |
| `README.md` | 同步 RAG 模块边界 |
| `docs/progress.md` | 本任务状态 |

## 兼容要求

- `format_rag_chunks_for_system()` 仍可用，或提供兼容导出。
- `RagChunk` 旧构造方式不破坏现有测试。
- `QDRANT_MOCK=true` 行为保持。
- dense embedding 失败后 BM25 fallback 行为保持。
- `role_id` 过滤必须在 store adapter 层生效，service 层测试也要覆盖防越权。

## 非范围

- 不改变 RAG 质量算法目标；这是结构重构，不是新召回策略。
- 不引入外部搜索服务。
- 不改变 KB ingest API。
- 不改 Supervisor prompt。

## 测试方案

```bash
cd agent
uv run pytest tests/test_rag_retrieval.py tests/test_kb_ingest.py tests/test_rag_subagent.py tests/test_evals_seed.py -v
uv run pytest tests -v
uv run ruff check src tests
```

## 完成标准

- [ ] RAG 逻辑从单一大文件拆成可读模块。
- [ ] `rag.retriever` 作为兼容 facade 保持现有导入可用。
- [ ] dense、BM25、merge、rerank、role_id 过滤均有独立测试。
- [ ] 现有 RAG eval seed smoke test 通过。
- [ ] README 与 `docs/progress.md` 同步。

## 进度更新

`docs/progress.md` **45** → 实现完成后改为 `✅`。
