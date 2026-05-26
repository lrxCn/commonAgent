# 85 - 演示平台 Phase 1：学生 CRUD（Back API + Front 页）

## 建议执行模型

- 模型：GPT-5 或同档强编码模型
- Reasoning：medium
- 原因：标准 CRUD + 表格 UI + 409 冲突处理；演示平台 **MVP 里程碑**。

## 新窗口执行规则

1. 先读 PRD 模块四（学生管理）与 API `/api/students`。
2. 核对 **81**、**82**、**84** 已完成。
3. 学生数据 **全员共享**，不做行级过滤。

## 依赖

81, 82, 84

## 背景

学生管理证明 Back 是真实业务网关，**不调用 Agent**。任意登录用户可 CRUD 全表；`created_by` 仅审计。

## 目标

- Back：`GET/POST/PATCH/DELETE /api/students`（及可选 `POST .../batch-delete`）；分页 `offset/limit`；`student_no` 唯一 → **409** + `field_errors`。
- Front：`StudentsView`（`/app/students`）：`n-data-table`、搜索（姓名/学号/班级）、筛选、抽屉表单、Popconfirm 删除。
- 侧边栏「学生管理」对所有人可见。

## 范围

| 模块 | 变更 |
|------|------|
| `back/src/` | students 路由、schemas、service |
| `back/tests/` | CRUD、409、401 |
| `front/src/views/StudentsView.vue` | 或等价路径 |
| `front/src/api/students.ts` | typed API |

## 验证方案

```bash
cd back && uv run pytest tests/test_demo_students.py -v
cd front && npm run build
```

演示脚本 A 第一步可在此任务后手工验证。

## 非范围

- Agent 调用
- 学生行级权限（PRD 二期）
- RAG / 对话（后续任务）

## 完成标准

- [ ] alice 可新建学生；admin 可见同一列表并编辑/删除。
- [ ] 学号冲突返回可读 409。
- [ ] progress **85** → `✅`；可在 progress 备注「演示 MVP（学生）可达」。

## 进度更新

完成后建议下一步 **86** 或并行启动 **87**（Agent 契约，与 Front 无硬依赖）。
