# 97 - KB 多角色：Postgres 与 Qdrant 数据迁移

## 建议执行模型

- 模型：GPT-5 或同档强编码模型
- Reasoning：high
- 原因：合并旧 `(doc_id, role_id)` meta 行与 Qdrant payload 改写；需可回滚或幂等。

## 新窗口执行规则

1. 先读 PRD §迁移 M1–M2；确认 **93**、**95** 代码已支持新契约与 M1 双读。
2. 本任务执行**数据面**迁移；不在此任务做 M3 去兼容（留 **98** 文档说明或后续）。
3. 提供可本地运行的 migration 脚本/CLI + 测试；勿提交 secrets。
4. 完成后更新 progress 并 commit。

## 依赖

93, 95

## 背景

代码双读（M1）上线后，存量数据仍为旧形态：Postgres 同一 `doc_id` 多行 meta、Qdrant payload 单 `role_id`。需合并为一条 meta + junction 多行，并将 points payload 改为 `role_ids: [原 role_id]`（或并集）。

## 目标

### Postgres

- 迁移脚本：对同一 `doc_id` 的多行旧 meta **合并**为一条：
  - `role_ids` = 所有旧 `role_id` 并集写入 `kb_document_roles`。
  - `doc_name` / `version` / `raw_content` 等冲突字段取 `updated_at` 最新。
- 删除重复 meta 行；保证 `doc_id` PK 唯一。
- Alembic revision 或独立 `back/scripts/migrate_kb_multi_role.py`（二选一或组合）；**幂等**或可 dry-run。

### Qdrant

- Scroll collection：将 `role_id` → `role_ids: [role_id]`（同一 `doc_id` 的 points 写入相同并集 `role_ids`）。
- 可选：删除旧 `role_id` 字段（建议保留至 **98** 文档化 M3 前）。

### 验证

- 迁移前 ingest 的单角色文档：迁移后 retrieve 行为不变。
- 曾重复 ingest 同 doc 不同 role 的行：合并后 sales/support 用户均可 retrieve。

## 范围

| 模块 | 变更 |
|------|------|
| `back/alembic/versions/` 或 `back/scripts/` | 数据迁移 |
| `agent/scripts/` 或 `back/scripts/` | Qdrant payload 迁移 |
| `back/tests/` | 迁移逻辑单元测试（SQLite fixture） |
| `agent/tests/` | 可选 mock Qdrant scroll 测试 |

## 验证方案

```bash
cd back && uv run pytest tests/test_kb_migration.py -v
# 若脚本独立：
cd back && uv run python scripts/migrate_kb_multi_role.py --dry-run
cd agent && uv run pytest tests/test_kb_ingest.py tests/test_role_ids_filter.py -v
```

本地无 Qdrant 时：至少跑 Postgres 合并逻辑的 unit test + 文档说明 Qdrant 脚本用法。

## 非范围

- 移除代码中对旧 `role_id` 的读取 fallback（M3，**98** 可记录计划）
- Front / 新功能
- README 大改（**98**）

## 完成标准

- [ ] 迁移脚本可 dry-run；Postgres 合并逻辑有测试覆盖。
- [ ] Qdrant 脚本或文档化步骤可将 payload 升级为 `role_ids[]`。
- [ ] progress **97** → `✅`；git commit。

## 进度更新

建议下一步 **98**（文档最终对齐）。
