# 86 - 演示平台 Phase 2a：账号管理（角色与用户 CRUD）

## 建议执行模型

- 模型：GPT-5 或同档强编码模型
- Reasoning：medium
- 原因：多对多角色、admin 保护规则与 409 删除约束需要仔细对齐 PRD。

## 新窗口执行规则

1. 先读 PRD 模块二、工具白名单段（为 **88** 预留，本任务可不改 Agent）。
2. 核对 **81**、**82**、**84** 已完成。

## 依赖

81, 82, 84

## 背景

管理员维护 `role-*` 角色与普通用户；用户可绑定 **多个** `role_id`，无「主角色」，全量写入 `user_roles` 并作为未来 `role_ids[]` 来源。

## 目标

- Back admin API：`/api/admin/roles`、`/api/admin/users`；非 admin → **403**。
- 角色：`role_id` 创建后不可改；格式 `role-[a-z0-9-]+`；删除时仍有用户或 KB 文档 → **409**。
- 用户：创建/编辑至少选一个角色；**不可删除 admin** 或取消其 `is_admin`。
- Front：`RolesView`、`UsersView`；admin 侧边栏显示账号菜单。
- 列表聚合：角色「用户数」、文档数可先占位 0 或简单 count（KB 计数在 **89** 完善）。

## 范围

| 模块 | 变更 |
|------|------|
| `back/src/admin/` | roles、users 路由与服务 |
| `back/tests/test_demo_admin.py` | 权限、409、admin 保护 |
| `front/src/views/admin/` | 角色、用户管理页 |
| `back/config/tools.demo.json` | 确认 `role-admin` 等 roles 字段（若需调整，与 PRD 示例一致） |

## 验证方案

```bash
cd back && uv run pytest tests/test_demo_admin.py -v
cd front && npm run build
```

## 非范围

- `role_ids[]` 注入 Agent（**88**）
- RAG 文档 UI（**90**）
- 扩展 `context.py` 多角色并集（**88**）

## 完成标准

- [ ] admin 可 CRUD 角色与用户；普通用户 403 admin API。
- [ ] 多角色用户保存后 `/api/me` 返回完整 `role_ids`。
- [ ] progress **86** → `✅`。

## 进度更新

完成后建议下一步 **87**（若未完成）→ **88**。
