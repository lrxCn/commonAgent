# 95 - KB 多角色：Back 库表迁移与 Admin KB API `role_ids[]`

## 建议执行模型

- 模型：GPT-5 或同档强编码模型
- Reasoning：high
- 原因：Alembic 改主键、新建 junction、Admin API 契约与 Agent 双写需与 **89** 现有 meta 逻辑衔接。

## 新窗口执行规则

1. 先读 PRD §D2、§Back Admin API；对照 `back/src/admin/kb.py`、`kb_routes.py`、`services/agent_kb.py`。
2. 核对 **93** 已完成（Agent 已接受 `role_ids[]`）。
3. **93** 未完成时可先写 migration/models，但 API 联调须等 Agent 契约就绪。
4. 测试通过后更新 progress 并 commit。

## 依赖

93

## 背景

当前 `kb_document_meta` 联合主键 `(doc_id, role_id)`，同一逻辑文档授多角色需重复 ingest。PRD 改为 `doc_id` 唯一主键 + `kb_document_roles` 多对多 junction；Admin API 入参/出参统一 `role_ids[]`。

## 目标

### 数据库

- Alembic：新建 **`kb_document_roles`**（`doc_id` + `role_id` 联合 PK，FK CASCADE）。
- 调整 **`kb_document_meta`**：以 `doc_id` 为唯一 PK（迁移脚本在 **97** 合并旧行；本任务可先建新表结构 + 代码读新模型，或含基础 forward migration）。
- ORM models 与 **89** seed 兼容。

### Admin API（`/api/admin/kb/documents`）

- `POST`：`role_ids[]` 必填（≥1），校验各 role 存在于 `roles` 表 → 转发 Agent ingest `{ role_ids[] }` → 成功 upsert meta + junction。
- `GET` 列表：item 含 `role_ids[]`（junction 聚合）；query `role_id` 筛选语义为「文档 `role_ids` **包含**该角色」。
- `GET /{doc_id}`：**移除** query `role_id`；返回 meta + Agent chunk 预览。
- `PATCH /{doc_id}`：可选 `role_ids` 全量替换（≥1）；触发 re-ingest（PRD 一期简化）。
- `DELETE /{doc_id}`：**移除** query `role_id`；删 Agent points + meta + junction。

### Agent 转发

- `services/agent_kb.py`：请求/响应字段改为 `role_ids[]`；错误体透传。

## 范围

| 模块 | 变更 |
|------|------|
| `back/alembic/versions/` | junction + meta PK 变更 |
| `back/src/db/models.py` | `KbDocumentMeta`、`KbDocumentRole` |
| `back/src/admin/kb.py` | CRUD + junction |
| `back/src/admin/kb_routes.py` | 契约 |
| `back/src/services/agent_kb.py` | `role_ids[]` 转发 |
| `back/tests/test_demo_kb.py`、`test_kb_admin_api.py` | 多角色 meta |

## 验证方案

```bash
cd back && uv run pytest tests/test_demo_kb.py tests/test_kb_admin_api.py -v
cd back && uv run alembic upgrade head
cd back && uv run ruff check src tests
```

## 非范围

- Postgres/Qdrant **历史数据**合并（**97**）
- Front UI（**96**）
- 角色管理页「文档数」统计口径（可在 **98** 文档注明，或本任务顺手改 junction count）
- README（**98**）

## 完成标准

- [ ] 新建文档写入 meta 一条 + junction 多行；API 返回 `role_ids[]`。
- [ ] PATCH 改 `role_ids` 后 junction 与 Agent 一致。
- [ ] DELETE 仅需 `doc_id`。
- [ ] pytest 通过；progress **95** → `✅`；git commit。

## 进度更新

建议下一步 **96**。
