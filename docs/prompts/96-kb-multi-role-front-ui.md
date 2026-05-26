# 96 - KB 多角色：Front RAG 管理页多选角色

## 建议执行模型

- 模型：GPT-5 或同档强编码模型
- Reasoning：medium
- 原因：Naive UI 表单与 API 类型对齐；无复杂 graph 逻辑。

## 新窗口执行规则

1. 先读 PRD §前端、`KbDocumentsView.vue`、`front/src/api/kb.ts`、`types/index.ts`。
2. 核对 **95** 已完成（Back API 已返回 `role_ids[]`）。
3. 只改 KB 管理相关 Front 文件。
4. 测试：`npm run build` + 手动验收清单；通过后更新 progress 并 commit。

## 依赖

95

## 背景

演示平台 RAG 管理页（任务 90）角色为单选 `role_id`。本任务改为多选，与 Back/Agent `role_ids[]` 契约一致。

## 目标

| 区域 | 变更 |
|------|------|
| 新建抽屉 · 角色 | `NSelect` **multiple + filterable**；校验至少 1 项 |
| 详情抽屉 · 角色 | 同上，预填当前 `role_ids`，可编辑 |
| 列表 · 角色列 | 多个 `NTag` |
| 筛选 | 保持单选角色；语义「包含该角色」 |
| 删除确认 | 展示全部 `role_ids`，去掉单 `role_id` 文案 |
| Types / API | `KbDocument.role_id` → **`role_ids: string[]`**；POST/PATCH body 同步 |

## 范围

| 模块 | 变更 |
|------|------|
| `front/src/views/admin/KbDocumentsView.vue` | 多选 UI |
| `front/src/api/kb.ts` | 请求/响应类型 |
| `front/src/types/index.ts` | `KbDocument` |

## 验证方案

```bash
cd front && npm run build
cd front && npm run type-check 2>/dev/null || npx vue-tsc --noEmit
```

手动验收（Back + Agent 已启动）：

- [ ] 新建文档勾选 sales + support，列表显示两 Tag，chunks 只 ingest 一次。
- [ ] 编辑增删角色后保存，详情与列表一致。
- [ ] 单角色筛选返回包含该角色的多角色文档。

## 非范围

- Chat / thread_id（**99**）
- 登录页交互（**100**）
- 用户管理员开关（**101**）
- README / walkthrough（**98**）

## 完成标准

- [ ] Front 不再发送单值 `role_id` 业务字段。
- [ ] build 与类型检查通过。
- [ ] progress **96** → `✅`；git commit。

## 进度更新

建议下一步 **97**（迁移）或并行 **99–101** 小迭代。
