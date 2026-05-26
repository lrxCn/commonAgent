# 82 - 演示平台 Phase 0b：Back Cookie Session 与认证 API

## 建议执行模型

- 模型：GPT-5 或同档强编码模型
- Reasoning：medium
- 原因：Session 安全、CORS 与 `/api/me` 契约需与 PRD 一致，并作为后续所有 Back API 的前置。

## 新窗口执行规则

1. 先读 `AGENTS.md`、`README.md`、`docs/progress.md`、本任务卡与 PRD `demo-admin-console.md` 模块一、API 认证段。
2. 核对 **81** 已完成。
3. 只实现认证与会话，不做业务 CRUD 页面。
4. 测试通过后更新 `docs/progress.md`。

## 依赖

81

## 背景

演示平台鉴权为 **HttpOnly Cookie Session**（`SameSite=Lax`）。Front 使用 `axios` + `withCredentials: true`；**禁止** Front 自报 `user_id`/`role_ids`。

## 目标

- `POST /api/auth/login`：校验用户名密码（bcrypt）；成功 `Set-Cookie`。
- `POST /api/auth/logout`：清 Session。
- `GET /api/me`：返回 `user_id`、`username`、`display_name`、`is_admin`、`role_ids[]`、`roles[]`（见 PRD 示例）。
- 未登录访问需登录的路由依赖项 → **401**；统一错误体格式（PRD）。
- `CORS_ORIGINS` 含 `http://127.0.0.1:5173` 与 `http://localhost:5173`；允许 credentials。

## 范围

| 模块 | 变更 |
|------|------|
| `back/src/` | Session 中间件/依赖、`auth` 路由 |
| `back/.env.example` | `SESSION_SECRET`、`CORS_ORIGINS` |
| `back/tests/` | login/logout/me、错误密码、未登录 401 |

## 实施步骤

1. Session 存储：单机 demo 可用 signed cookie + server-side session 表或内存（PRD 开放问题 #3 默认 signed cookie）。
2. 登录失败统一文案：「用户名或密码错误」。
3. 从 `user_roles` 加载全量 `role_ids`（去重、保序）。

## 验证方案

```bash
cd back && uv run pytest tests/test_demo_auth.py -v
```

手动（可选）：curl login 后带 Cookie 调 `/api/me`。

## 非范围

- Vue 登录页（**84**）
- admin CRUD（**86**）
- `POST /api/chat`（**88**）

## 完成标准

- [ ] admin / alice / bob（若 81 已种子）可登录并拿到正确 `role_ids`。
- [ ] logout 后 `/api/me` 为 401。
- [ ] CORS + credentials 测试或文档注明手动验证步骤。
- [ ] progress **82** → `✅`。

## 进度更新

完成后建议下一步 **83** 或 **84**（可与 83 并行，但 84 依赖 82+83）。
