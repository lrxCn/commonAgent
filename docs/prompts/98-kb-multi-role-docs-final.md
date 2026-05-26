# 98 - KB 多角色：README、演示手册与文档最终对齐

## 建议执行模型

- 模型：GPT-5 或同档强编码模型
- Reasoning：medium
- 原因：需核对 93–97 实际落地，同步 README、maps、PRD 与 progress；避免计划写成事实。

## 新窗口执行规则

1. 先读 `AGENTS.md`、当前 `README.md`、`docs/progress.md` 与本任务卡。
2. 阅读 PRD：[kb-multi-role-rag.md](../prd/kb-multi-role-rag.md)。
3. 核对 **93–97** 均已完成；否则停止。
4. **只做文档与契约对齐**，不新增业务功能（M3 去兼容若未做，须在 PRD/README 标明「迁移期双读」现状）。
5. 关键 smoke 测试后更新 progress 并 commit。

## 依赖

93, 94, 95, 96, 97

## 背景

KB 多角色批次（93–97）改变 Admin KB 与 Qdrant payload 契约：单 `role_id` → **`role_ids[]`**，`kb_document_meta` + **`kb_document_roles`**。本任务为该批次 **最终对齐**，模式同历史 48/57/62/68/74/80/92。

## 目标

- **README.md**：
  - Admin KB API 表：`role_ids[]` 入参/出参；GET/DELETE 不再要求 query `role_id`。
  - Agent internal KB API 同步。
  - Qdrant payload 字段说明：`role_ids[]` + 迁移期 fallback（若仍保留）。
  - `role-admin` / `is_admin` 若 **101** 已完成则一并写清推导规则。
- **docs/demo-walkthrough.md**：增加多角色 KB 演示步骤（admin 上传 sales+support；alice/bob 均可命中）。
- **docs/maps/**：更新 `rag-flow.md`、`demo-platform.md` KB meta/junction 与多角色数据流。
- **docs/prd/kb-multi-role-rag.md**：补充「落地状态 / 偏差 / 开放问题决议」小节。
- **docs/progress.md**：93–98 全部 `✅`；总任务数 101；changelog 记录 KB 多角色批次收口。

## 范围

| 模块 | 变更 |
|------|------|
| `README.md` | KB API 与 RAG payload 契约 |
| `docs/demo-walkthrough.md` | 多角色 KB 脚本 |
| `docs/maps/rag-flow.md`、`demo-platform.md` | 数据流 |
| `docs/prd/kb-multi-role-rag.md` | 落地状态 |
| `docs/progress.md` | 总览、93–98、changelog |

## 验证方案

```bash
rg -n "role_ids" README.md back agent/src front/src/api/kb.ts
rg -n "kb_document_roles|role_id.*query" README.md back
cd agent && uv run pytest tests/test_kb_ingest.py tests/test_role_ids_filter.py -v
cd back && uv run pytest tests/test_demo_kb.py -v
cd front && npm run build
```

## 非范围

- 新功能、M3 强制删除旧 fallback（除非 97 已做且需文档化「已完成」）
- 修改 `AGENTS.md` 治理顺序（除非用户明确要求）
- 小迭代 **99–101**（独立任务，可在 progress 中并行标注）

## 完成标准

- [ ] README 仅描述已落地事实；KB 契约以 `role_ids[]` 为主。
- [ ] demo-walkthrough 可演示多角色 KB 检索。
- [ ] PRD 有落地状态与已知偏差。
- [ ] progress **98** → `✅`；KB 多角色主批次（93–98）完成。
- [ ] git commit。

## 进度更新

`docs/progress.md` **98** → `✅`；建议下一步 **99**、**100** 或 **101**（三者无依赖，可任选）。
