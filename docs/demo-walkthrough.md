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
# 配置 VOLC_ASR_ACCESS_KEY（通话字幕，见 back/.env.example）及其他变量后：
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

### B4b — createStudent / listStudents 对话内学生工具（client_actions）

1. **alice** 登录 → 在首页对话抽屉发送：「帮我新建一个学生，姓名张三，学号 2024999」。
2. 期望：SSE/JSON 含 `client_actions`，`tool: "createStudent"`、`args` 含姓名/学号（或部分字段）；对话内出现**新建学生表单**（已预填），无「确认打开」步骤。
3. 点击「确定」→ Front POST `/api/students` → 成功 toast；**同一对话内**自动出现学生列表卡片（默认第一页，不回流 Agent）。
4. 发送：「查一下学生列表」或带搜索条件的话术 → 期望 `listStudents` action；列表可翻页、搜索；ChatDrawer **保持打开**。
5. 关闭并重新打开对话抽屉 → 历史中的表单/列表为 **historical**（只读，不可提交或翻页）。
6. 侧栏进入 `/app/students` → 传统 CRUD 表格仍可用（与对话内工具独立）。

### B5 — 账号 WebRTC 音频通话（双浏览器，约 3–5 分钟）

**目标**：演示系统内两账号 1:1 语音通话；信令经 Back WebSocket，**不经过 Agent**。

**准备**：两个浏览器（或两个 Profile / 无痕 + 普通窗口），均访问 `http://127.0.0.1:5173`。允许麦克风权限（接听时需用户手势）。

1. **浏览器 A**：**alice** / `demo123` 登录 → 侧边栏 **通话**（`/app/calls`）→ 列表中找到 **bob** → 点击 **呼叫**。
2. **期望（A）**：状态为「正在呼叫 bob…」；可点 **取消呼叫** 恢复 idle。
3. **浏览器 B**：**bob** / `demo123` 登录 → 停留在 **学生管理**（`/app/students`，不必打开通话页）。
4. **期望（B）**：左下角出现来电条（`IncomingCallToast`）：显示 Alice 来电、「语音通话」、**接听** / **拒接**。
5. **拒接路径**：B 点 **拒接** → 弹窗消失、不申请麦克风；A 显示「对方已拒接」并回到 idle。
6. **接听路径**：B 再次由 A 呼叫 → B 点 **接听** → B 跳转 `/app/calls`；A 进入「通话中」并显示计时。
7. **音频**：双方对着麦克风说话（可选戴耳机防回声）；确认能听到对方声音（依赖 NAT/STUN，极少数网络需自建 TURN，一期未包含）。
8. **挂断**：任一方点 **挂断** → 双方 UI 回到 idle，麦克风释放。
9. **Network 核对**：仅 `GET /api/calls/peers`、升级 `WS /api/calls/ws`（dev 下经 Vite proxy）；**无** 请求 Agent `:18080`。

### B6 — 通话实时字幕（双浏览器，约 3–5 分钟）

**目标**：在 **B5 通话** 基础上展示 CallsView 火山 SAUC 实时字幕；挂断后在浏览器控制台输出分角色 transcript。**不**写入 Chat / Agent。

**前提**：`back/.env` 已配置 `VOLC_ASR_ACCESS_KEY`（新控制台 API Key → `X-Api-Key`）；ASR 2.0 账号默认 `VOLC_ASR_RESOURCE_ID=volc.seedasr.sauc.duration`（1.0 改为 `volc.bigasr.sauc.duration`）。详见 [volcengine-streaming-asr.md](./prd/volcengine-streaming-asr.md)。

**准备**：同 B5（双浏览器、麦克风权限）。

1. **浏览器 A**：**alice** 登录 → **通话** → 呼叫 **bob**。
2. **浏览器 B**：**bob** 登录 → 接听（可不在通话页，来电 toast 即可）。
3. **期望**：双方进入 `in_call` 后，CallsView 出现 **实时字幕** 面板（「我说 / 对方说」两栏）；说话时 partial 闪烁、final 句追加到对应栏。
4. **对话**：A 说「你好，能听到吗？」→ A 的「我说」栏更新；B 回应 → A 的「对方说」栏更新（双轨 ASR，各端采集本地 + 远端流）。
5. **Network**：除 `WS /api/calls/ws` 外，应有 **`WS /api/asr/ws`**；PCM 为 WebSocket binary 帧（前置 JSON `asr.track`）；**仍无** Agent `:18080`。
6. **挂断**：任一方点 **挂断** → 字幕区清空。
7. **控制台**：双方 DevTools Console 应出现 `console.group('[Call Transcript] …')`，行前缀如 `[本地 · Alice]`、`[对方 · Bob]`（按 track 与 display_name）。
8. **凭证缺失**：若未配置 `VOLC_ASR_ACCESS_KEY`，字幕区显示可读 warning，**WebRTC 通话本身不受影响**。

### B7 — 边界核对（可选，1 分钟）

- 浏览器 Network：对话与学生 API 仅指向 Back（`:8080` 或 dev proxy），**无** 直连 Agent `:18080`。
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
| createStudent 无反应 | 是否点击表单「确定」；Console 是否有参数校验 toast；POST `/api/students` 是否 2xx |
| listStudents 无数据 | create 成功后是否自动出现列表卡片；单独 list 话术是否产出 action；Network 是否 GET `/api/students` |
| admin 无 RAG 菜单 | 当前用户 `is_admin`；种子 admin 绑定 `role-admin` |
| 通话无来电弹窗 | bob 是否已登录且 WS 已连（`AppLayout`）；Console 是否有 WS 错误；Back 是否单进程 |
| 呼叫一直响铃 | 被叫是否拒接/离线；A 是否收到 `call.failed`；检查 `test_call_signaling.py` 是否绿 |
| 接通无声音 | 浏览器麦克风权限；是否 HTTPS/localhost；对称 NAT 下可试配置 `VITE_WEBRTC_STUN_URL` |
| 多标签同账号 | 后连 WS 会踢前者（`session.replaced`）；仅保留一个活跃标签通话 |
| 字幕无更新 | `back/.env` 是否配置 `VOLC_ASR_ACCESS_KEY`；Console 是否有 `asr.error`；Network 是否连上 `WS /api/asr/ws` |
| 字幕有但控制台无 transcript | 是否产生 `asr.final` 句；挂断后查看 Console 的 `[Call Transcript]` group |
| ASR 报错但通话正常 | 预期行为：ASR 失败不阻断 WebRTC；检查火山凭证与 `test_asr_ws.py` |

更细的 Back/Front 路由与数据流见 [docs/maps/demo-platform.md](./maps/demo-platform.md)。
