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

## 脚本 B — RAG 多角色 + 对话（约 10–12 分钟）

**目标**：展示文档级 `role_ids[]`、用户 Session `role_ids[]` 注入、payload 交集检索隔离、多角色同文档共享，以及 `client_actions`。

### B1 — 上传单角色与多角色知识库（admin）

1. **admin** 登录 → 侧边栏 **RAG 管理**（`/app/admin/kb`）。
2. **仅 sales**：新建文档，角色多选勾选 **role-sales**，上传 `产品价目表.md`（含「标准版一年 3999 元」等可检索事实）。
3. **仅 support**：再建一条，仅勾选 **role-support**，上传 `退换货政策.md`（含「7 天内可退货」等）。
4. **sales + support 共享**：再建一条，**同时勾选 role-sales 与 role-support**，上传 `公司通用 FAQ.md`（含双方都关心的通用条款，如「客服热线 400-xxx」）。
5. 列表中每条记录以 **Tag 展示 `role_ids[]`**（非单 `role_id`）；点开详情可见 chunk 概览；正文存 Back `kb_document_meta.raw_content`，向量在 Qdrant。

### B2 — 销售角色对话（alice）

1. 退出后以 **alice** 登录（Session 仅 `role-sales`）。
2. 任意页点击右下角 FAB → **对话抽屉**（约 420px）。
3. 提问：「标准版一年多少钱？」
4. 期望：命中 **sales 价目表** 或 **共享 FAQ**；**不应**引用仅 support 的退换货政策。
5. 再问共享 FAQ 中的事实（如客服热线），期望能命中 **B1 步骤 4** 的多角色文档。
6. （可选）新开 thread（清空 sessionStorage `thread_id` 或刷新）避免旧上下文干扰。

### B3 — 支持角色对话（bob）

1. **bob** 登录（仅 `role-support`）→ 打开对话抽屉。
2. 提问：「买错了可以退吗？」或「几天可以退货？」
3. 期望：命中 **support 政策** 或 **共享 FAQ**；**不应**出现仅 sales 的价目表细节。
4. 用与 alice 相同的话术问共享 FAQ，期望 **同一 doc_id** 内容对 bob 也可检索（文档 `role_ids` 与用户角色有交集）。

### B3b — 多角色文档边界（可选，1 分钟）

- 若存在 **仅绑定 role-admin** 的测试文档（种子外手工上传），alice/bob 对话应 **无法** 命中该文档（用户 `role_ids` 与文档 `role_ids` 无交集）。

### B4 — jumpPage 页面跳转（client_actions）

1. **admin** 登录 → 对话抽屉。
2. 发送：「请打开 RAG 管理页面」或「跳转到 RAG 管理」。
3. 期望：SSE/JSON 含 `client_actions`，`tool: "jumpPage"`、`args.page: "admin-kb"`；对话内出现**跳转确认卡片**；点击「确认跳转」后 URL 变为 `/app/admin/kb` 且 ChatDrawer **关闭**；点「取消」则不跳转。
4. 退出后以 **alice**（`role-sales`）登录 → 发送：「打开学生管理」。
5. 期望：进入 `/app/students`。
6. alice 再发送：「打开用户管理」。
7. 期望：Agent 可能产出 `admin-users`；Front 拦截（与 `requiresAdmin` guard 一致）→ toast「当前账号无权访问该页面」，**停留当前页**。
8. Network 仍只打 Back，无直连 Agent。

### B5 — 边界核对（可选，1 分钟）

- 浏览器 Network：请求仅指向 Back（`:8080` 或 dev proxy），**无** 直连 Agent `:18080`。
- 用另一用户 thread_id 拉历史应 **403**（`chat_threads` 归属校验）。

---

## 故障排查

| 现象 | 检查 |
|------|------|
| 登录 401 / CORS | `back/.env` `CORS_ORIGINS` 含 `http://127.0.0.1:5173`；Front `withCredentials` |
| 学生列表空 | `uv run alembic upgrade head && uv run python -m db.seed` |
| RAG 无命中 | Qdrant 可达；文档 `role_ids[]` 与用户 Session `role_ids[]` **有交集**；存量库可跑 `agent/scripts/migrate_kb_role_ids.py`；Agent `QDRANT_MOCK=false` |
| 对话无流式 | Agent 已启动；`AGENT_URL` 正确；Back 日志无转发超时 |
| jumpPage 无跳转 | alice/admin 角色是否在 `tools.demo.json` 白名单；Console 是否有未知 slug toast |
| admin 无 RAG 菜单 | 当前用户 `is_admin`；种子 admin 绑定 `role-admin` |

更细的 Back/Front 路由与数据流见 [docs/maps/demo-platform.md](./maps/demo-platform.md)。
