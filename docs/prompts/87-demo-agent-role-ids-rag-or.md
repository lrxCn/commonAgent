# 87 - 演示平台 Phase 2b：Agent `role_ids[]` 契约与 RAG OR 检索

## 建议执行模型

- 模型：GPT-5 或同档强编码模型
- Reasoning：high
- 原因：触及 RequestContext、graph context、Qdrant/BM25 filter 与既有 RAG 测试；需保持 graph 拓扑不重构。

## 新窗口执行规则

1. 先读 `agent/AGENTS.md`、`README.md` RAG/context 段、PRD「Context 契约扩展」「Agent 改造」。
2. 核对 Agent 基础任务已完成；可与 **86** 并行，但 **88** 依赖本任务。
3. **不重构** Supervisor 图拓扑；仅薄扩展契约与 retriever filter。

## 依赖

无（Agent 侧；与 Back/Front 并行）

## 背景

PRD 将单 `role_id` 扩展为 **`role_ids[]`**。RAG 语义：检索时对绑定集合 **OR 合并**（Qdrant `should` 多条件）。可保留 `role_id` 作为 `role_ids[0]` 的 deprecated alias **一版**，测试通过后移除（可在本任务或 **92** 文档注明）。

## 目标

- `RequestContext` / gateway schemas：`role_ids: list[str]`，校验非空、去重。
- Graph `context_schema` 与节点消费 `role_ids`。
- `rag/retriever`（及 Qdrant payload filter）：**任一** `role_id` 匹配即命中；补/改 **role 越权**  characterization 测试。
- README **不在本任务大改**（留 **92**）；可在 progress 备注契约变更待文档化。

## 范围

| 模块 | 变更 |
|------|------|
| `agent/src/gateway/schemas.py` | `role_ids` |
| `agent/src/graph/context.py` 等 | 传递 `role_ids` |
| `agent/src/rag/retriever.py`、Qdrant filter | OR 逻辑 |
| `agent/tests/` | 单角色隔离、多角色 OR、deprecated alias（若保留） |

## 验证方案

```bash
cd agent && uv run pytest tests/test_schemas.py tests/test_rag_retrieval.py tests/test_role_id_isolation.py -v
# 若无 test_role_id_isolation，新增 tests/test_role_ids_filter.py
cd agent && uv run ruff check src tests
```

## 非范围

- Back `POST /api/chat` 注入（**88**）
- KB list/delete API（**89**）
- README 最终对齐（**92**）

## 完成标准

- [ ] ingest payload 仍为单 doc 单 `role_id`；检索支持多 `role_ids` OR。
- [ ] 单角色用户行为与改前隔离一致。
- [ ] progress **87** → `✅`。

## 进度更新

完成后建议下一步 **88**。
