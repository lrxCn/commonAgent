# 40 - RAG 质量提升：sparse/BM25 与评测闭环

## 依赖

20, 39

## 背景

当前 RAG 使用 dense + payload text fallback + rerank，能跑但质量有限。需要建立 sparse/BM25 召回和评测闭环。

## 目标

- 补真实 sparse 查询或 BM25 服务/实现。
- 用评测 seed / LangSmith Dataset 比较改动前后效果。
- 增加 role_id 权限召回测试，防止越权。

## 范围

| 模块 | 变更 |
|------|------|
| `agent/src/rag/retriever.py` | 接入 sparse query 或 BM25 fallback |
| `agent/src/rag/ingest.py` | 如需要，补 sparse 索引写入 |
| `agent/evals/` | 增加 RAG 问答评测样例 |
| `agent/tests/` | 覆盖召回、rerank、role_id 过滤 |
| `README.md` | 同步 RAG 质量与评测说明 |
| `docs/progress.md` | 本任务状态 |

## 非范围

- 不改 turn_type。
- 不改 Supervisor。
- 不引入重型搜索服务，除非先在任务说明中更新架构取舍。

## 测试方案

```bash
cd agent
uv run pytest tests/test_rag_retrieval.py tests/test_kb_ingest.py tests/test_evals_seed.py -v
```

## 完成标准

- [ ] RAG 评测集中知识库问题可跑。
- [ ] sparse/BM25 路径有测试。
- [ ] role_id 过滤不会越权召回。
- [ ] 评测结果能比较改动前后。
- [ ] README 与 `docs/progress.md` 同步。

## 进度更新

`docs/progress.md` **40** → 实现完成后改为 `✅`。

