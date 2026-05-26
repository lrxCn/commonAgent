# 90 - 演示平台 Phase 3b：Front RAG 管理页

## 建议执行模型

- 模型：GPT-5 或同档强编码模型
- Reasoning：medium
- 原因：admin 表单、文件上传与列表筛选；依赖 **89** API 稳定。

## 新窗口执行规则

1. 先读 PRD 模块三 UI 行为（列表、新建、详情、编辑、删除确认）。
2. 核对 **89**、**84**、**86** 已完成。

## 依赖

89, 84, 86

## 背景

仅 admin 可见「RAG 管理」。详情正文从 meta 回填；chunk 概览可调用 Agent get（仅 chunk 列表）。

## 目标

- `KbDocumentsView`（`/app/admin/kb`）：角色筛选、关键词搜索、表格列与 PRD 一致。
- 新建：选择 `role_id`、上传 txt/md 或粘贴 content。
- 详情/编辑：`raw_content` 预填；保存触发新版本 ingest。
- 删除：二次确认含 `doc_name` + `role_id`。

## 范围

| 模块 | 变更 |
|------|------|
| `front/src/views/admin/KbDocumentsView.vue` | 或拆分 Detail 组件 |
| `front/src/api/kb.ts` | admin KB API |

## 验证方案

```bash
cd front && npm run build
# 手动脚本 B 步骤 1：admin 为 role-sales / role-support 各上传一篇
```

## 非范围

- 对话抽屉 SSE（**91**）
- README / walkthrough（**92**）

## 完成标准

- [ ] admin 可完成上传、编辑、删除；非 admin 无菜单且 API 403。
- [ ] progress **90** → `✅`。

## 进度更新

完成后建议下一步 **91**。
