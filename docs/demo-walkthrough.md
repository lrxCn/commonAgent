# 演示平台操作手册

面向团队或访客的 **5 分钟 / 10 分钟** 演示脚本。前提：已按 [README.md](../README.md)「本地运行」完成 Agent → Back → Front 启动，且 Back 已执行迁移与种子。

## 环境准备（一次性）

```bash
# 1. Postgres：Agent 库 common_agent（含 pgvector）+ Back 库 common_agent_back
createdb common_agent_back   # 若实例上尚未创建

# 2. Agent
cd agent && cp .env.example .env && uv sync
# 配置 DATABASE_URL、LLM、Qdrant 等后：
uv run uvicorn src.main:app --host 127.0.0.1 --port 18080

# 3. Back
cd back && cp .env.example .env && uv sync
uv run alembic upgrade head
uv run python -m db.seed
uv run uvicorn src.main:app --host 127.0.0.1 --port 8080

# 4. Front（Vue SPA，默认 http://127.0.0.1:5173，proxy → Back :8080）
cd front && npm install && npm run dev
```

种子账号（与 PRD 一致）：

| 用户名 | 密码 | 角色 |
|--------|------|------|
| admin | 123456 | role-admin |
| alice | demo123 | role-sales |
| bob | demo123 | role-support |

---

## 脚本 A — 学生 CRUD（约 5 分钟）

**目标**：展示 Back 业务 API + Vue 管理界面；不涉及 RAG。

1. 浏览器打开 `http://127.0.0.1:5173`，使用 **alice** / `demo123` 登录。
2. 进入 **欢迎页**（`/app/home`），确认显示用户名与 `role-sales` 标签。
3. 侧边栏 **学生管理** → **新建**，填写学号、姓名等 → 保存。
4. 列表刷新后可见新记录；使用搜索/筛选验证。
5. 退出，用 **admin** / `123456` 登录 → 同一学生列表可 **编辑/删除**（一期全员共享表，无行级隔离）。
6. （可选）右下角 **对话 FAB** 打开抽屉，发一句寒暄，确认 SSE 有回复（不要求查学生数据）。

---

## 脚本 B — RAG 多角色 + 对话（约 10 分钟）

**目标**：展示 `role_ids[]` 注入、Qdrant OR 检索隔离、`client_actions` 与换账号对比。

### B1 — 上传分角色知识库（admin）

1. **admin** 登录 → 侧边栏 **RAG 管理**（`/app/admin/kb`）。
2. 为 **role-sales** 上传文本（如 `产品价目表.md`，内容含「标准版一年 3999 元」等可检索事实）。
3. 为 **role-support** 上传另一文档（如 `退换货政策.md`，内容含「7 天内可退货」等）。
4. 列表中确认两条记录 `role_id` 不同；点开详情可见 chunk 概览（原文在 Back `kb_document_meta`）。

### B2 — 销售角色对话（alice）

1. 退出后以 **alice** 登录（仅 `role-sales`）。
2. 任意页点击右下角 FAB → **对话抽屉**（约 420px）。
3. 提问：「标准版一年多少钱？」
4. 期望：回答引用 sales 文档；**不应**出现 support 文档内容。
5. （可选）新开 thread（抽屉内或刷新 session）避免旧上下文干扰。

### B3 — 支持角色对话（bob）

1. **bob** 登录 → 打开对话抽屉。
2. 提问：「买错了可以退吗？」或「几天可以退货？」
3. 期望：引用 support 文档；与 alice 结果隔离。

### B4 — Admin 工具与 client_actions

1. **admin** 登录 → 对话抽屉。
2. 发送：「请跳转到 pageA」或 PRD 中配置的跳转话术。
3. 期望：响应含 `client_actions`；浏览器 **Console** 出现工具日志（Front 演示为 confirm + console，不真跳转生产页）。

### B5 — 边界核对（可选，1 分钟）

- 浏览器 Network：请求仅指向 Back（`:8080` 或 dev proxy），**无** 直连 Agent `:18080`。
- 用另一用户 thread_id 拉历史应 **403**（`chat_threads` 归属校验）。

---

## 故障排查

| 现象 | 检查 |
|------|------|
| 登录 401 / CORS | `back/.env` `CORS_ORIGINS` 含 `http://127.0.0.1:5173`；Front `withCredentials` |
| 学生列表空 | `uv run alembic upgrade head && uv run python -m db.seed` |
| RAG 无命中 | Qdrant 可达；文档 `role_id` 与用户 `role_ids[]` 一致；Agent `QDRANT_MOCK=false` |
| 对话无流式 | Agent 已启动；`AGENT_URL` 正确；Back 日志无转发超时 |
| admin 无 RAG 菜单 | 当前用户 `is_admin`；种子 admin 绑定 `role-admin` |

更细的 Back/Front 路由与数据流见 [docs/maps/demo-platform.md](./maps/demo-platform.md)。
