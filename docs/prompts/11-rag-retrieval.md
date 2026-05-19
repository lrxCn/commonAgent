# 11 - RAG 检索管线

## 依赖

02, 10

## 目标

对 `rewritten_query` 在 Qdrant 做 **role_id 过滤** + dense + sparse + rerank，结果写入 `rag_chunks`。

## 范围

- `agent/src/rag/retriever.py`：`retrieve(role_id, query) -> list[RagChunk]`
- `RagChunk`: doc_id, chunk_id, text, score
- 主链路 **只查一次**；结果进 system 时带引用标识
- 无 Qdrant 时 `QDRANT_MOCK=true` 返回 fixture

## 非范围

- Ingest（20）
- SubAgent 二查（14）

## 实现要点

- collection 名来自 settings
- rerank 可插拔；记录 span metadata 供 LangSmith（21）

## 测试方案

```bash
cd agent
uv run pytest tests/test_rag_retrieval.py -v
```

mock：过滤 role_id；返回条数 ≤ top_k；chunk 含 doc_id。

## 完成标准

- `retrieve` 可被图节点调用
- 空库返回 `[]` 不抛错

## 进度更新

`docs/progress.md` **11** → `✅`
