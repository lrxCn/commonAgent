# 101 - 管理员身份由 role-admin 推导，移除重复开关

## 建议执行模型

- 模型：GPT-5 或同档强编码模型
- Reasoning：medium
- 原因：Back 用户 API 契约与种子用户约束；Front 表单简化。

## 新窗口执行规则

1. 先读 PRD §小迭代：管理员身份由角色推导。
2. 阅读 `UsersView.vue`、`back/src/admin/users.py`、`admin/routes.py`。
3. 路由鉴权仍读 `user.is_admin`；保存时由 `role_ids` 推导写入 DB。
4. pytest + build；更新 progress 并 commit。README 细述可留 **98** 若未做，或本任务窄更新 README 用户管理一句。

## 依赖

无（与 KB 批次独立；若 **98** 未做，本任务可在 README 补一句 `is_admin` 推导）

## 背景

用户表单同时有角色多选与「管理员」开关，易与 `role-admin` 不一致。目标：**绑定 `role-admin` ⇔ 管理员**，移除 Front 开关，Back 自动写 `is_admin`。

## 目标

### Front

- 删除 `formIsAdmin` 及「管理员」表单项。
- `createUser` / `updateUser` 请求体**不含** `is_admin`。
- 列表「管理员」列：读 `row.is_admin` 或 `row.role_ids.includes('role-admin')`（展示一致即可）。

### Back

- `create_user` / `update_user`：`_validate_role_ids` 后 `is_admin = ("role-admin" in role_ids)`。
- `UserCreateRequest` / `UserUpdateRequest`：**移除**客户端 `is_admin`（或 deprecated 忽略）。
- `_assert_admin_constraints`：种子 `u-admin` 必须保留 `role-admin`；不可删至非管理员。

### 文档（窄）

- 若 **98** 已完成：在 changelog 备注即可。
- 若 **98** 未做：README 用户管理段增加 `is_admin` 与 `role-admin` 同步说明一句。

## 范围

| 模块 | 变更 |
|------|------|
| `front/src/views/admin/UsersView.vue` | 移除开关 |
| `front/src/api/admin.ts` | 类型 |
| `back/src/admin/users.py` | 推导逻辑 |
| `back/tests/test_demo_admin.py` | 推导用例 |

## 验证方案

```bash
cd back && uv run pytest tests/test_demo_admin.py -v
cd front && npm run build
```

手动：

- [ ] 只选 `role-sales` → 非管理员，无法进 `/app/admin/*`。
- [ ] 含 `role-admin` → 管理员，可进后台。
- [ ] 编辑去掉/加上 `role-admin` → `is_admin` 自动变化。
- [ ] 表单无管理员开关；种子 admin 不可去掉 `role-admin`。

## 非范围

- OAuth、权限细粒度 ACL
- KB 多角色（93–98）

## 完成标准

- [ ] API 写接口不再依赖客户端 `is_admin`。
- [ ] 测试与 build 通过；progress **101** → `✅`；git commit。

## 进度更新

独立小迭代；全部 93–101 完成后 progress 总览 101/101。
