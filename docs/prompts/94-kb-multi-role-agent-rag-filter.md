# 94 - KB 多角色：Agent RAG 检索 payload `role_ids[]` 过滤

## 建议执行模型

- 模型：GPT-5 或同档强编码模型
- Reasoning：high
- 原因：扩展 Qdrant `roles_filter` 与 retriever 交集语义；需保持任务 87 对话 OR 行为不退化。

## 新窗口执行规则

1. 先读 `agent/AGENTS.md`、`README.md` RAG 段、PRD §D1 与 §迁移 M1。
2. 核对 **93** 已完成（ingest 已写 `role_ids[]` payload）。
3. 不重构 Supervisor 图；仅扩展 kb_store / retriever filter。
4. 测试通过后更新 progress 并 commit。

## 依赖

93

## 背景

任务 87 已实现**用户侧** `role_ids[]` OR 过滤，但 filter 仍匹配 payload 单字段 `role_id`。任务 93 写入 `role_ids[]` 后，检索需改为：用户角色集合与文档 payload `role_ids[]` **有任意交集**即命中；迁移期 fallback 读旧 `role_id` 单值。

## 目标

- `infrastructure/qdrant/kb_store.py`（或等价 `roles_filter`）：优先 `FieldCondition(key="role_ids", match=MatchAny(any=user_role_ids))`；若无命中或字段缺失，fallback 旧 `role_id in user_role_ids`（M1 双读）。
- `rag/retriever.py` / BM25 路径：与 dense 同一交集语义（若 BM25 有 role 过滤则同步）。
- 测试：
  - 多角色文档 + 单角色用户：有交集则命中。
  - 多角色文档 + 无交集用户：不命中。
  - 旧 payload 仅 `role_id`：fallback 仍命中。

## 范围

| 模块 | 变更 |
|------|------|
| `agent/src/infrastructure/qdrant/kb_store.py` | `role_ids[]` filter + fallback |
| `agent/src/rag/retriever.py` | 传递 filter 语义一致 |
| `agent/tests/test_role_ids_filter.py` 或 `test_rag_retrieval.py` | 多角色文档检索 |
| `agent/tests/test_kb_ingest.py` | 可选端到端 ingest→retrieve |

## 验证方案

```bash
cd agent && uv run pytest tests/test_role_ids_filter.py tests/test_rag_retrieval.py tests/test_kb_ingest.py -v
cd agent && uv run ruff check src tests
```

若 Qdrant 不可用，mock 路径仍须覆盖 filter 构造逻辑。

## 非范围

- 移除旧 `role_id` payload fallback（**97** 或 **98** 后 M3）
- Back / Front
- README 最终对齐（**98**）

## 完成标准

- [ ] 用户 `role_ids` 与文档 payload `role_ids` 交集非空即 retrieve 命中。
- [ ] 旧单 `role_id` payload 在 M1 窗口内仍可检索。
- [ ] pytest 通过；progress **94** → `✅`；git commit。

## 进度更新

建议下一步 **95**（可与 **94** 并行若 **93** 已完成，但 progress 推荐顺序 94→95）。
