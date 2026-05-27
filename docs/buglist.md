# Bug 清单

> 记录已知缺陷与待修复项；修复后改状态并可在 [progress.md](./progress.md) 变更日志中引用编号。  
> 设计/契约类 backlog 仍放各 PRD「开放问题」，本文件只跟踪**可复现的行为问题**。

## 状态说明

| 状态 | 含义 |
|------|------|
| `open` | 已确认，未排期 |
| `investigating` | 分析中 |
| `wontfix` | 已知且接受（需写理由） |
| `fixed` | 已修复（附 commit/任务卡） |

---

## 条目

| ID | 状态 | 模块 | 摘要 | 记录日期 |
|----|------|------|------|----------|
| [BUG-001](#bug-001-刷新后创建成功链式列表消失) | open | Front / Chat | 刷新后对话内「创建成功」自动追加的学生列表消失 | 2026-05-27 |
| [BUG-002](#bug-002-无单点登录) | open | Back / Front / Auth | 演示平台仅用户名密码 Cookie 登录，无企业单点登录（SSO） | 2026-05-27 |

---

### BUG-001：刷新后创建成功链式列表消失

| 字段 | 内容 |
|------|------|
| **状态** | open |
| **模块** | `front/src/stores/chat.ts`（对话内学生工具，任务 106–110） |
| **严重程度** | 中（功能可用，刷新/重开抽屉后体验断裂） |

**现象**

1. 在 ChatDrawer 内通过 `createStudent` 表单新建学生并提交成功。
2. 对话内自动出现 `listStudents` 表格（任务 110 链式 `appendListStudents`）。
3. 刷新页面或重新打开对话抽屉后，**列表卡片消失**；仅保留 Agent 下发的 `createStudent` 历史表单（`historical` 只读摘要）。

**复现**

- 账号：演示平台任意有 `createStudent` 白名单的角色（如 alice）。
- 话术示例：「创建学生张三 学号200 1年1班 在读」→ 点确定 → 见列表 → F5 刷新 → 打开智能对话 → 列表不见。

**根因**

- 创建成功后的列表由 Front **`appendListStudents()`** 本地追加，**不回流 Agent**，未写入 LangGraph checkpoint。
- `loadHistory()` 用服务端 `GET /api/threads/{id}/messages` **整表替换** `messages`，只还原 checkpoint 中的 `client_actions`（本回合仅有 `createStudent`）。
- 与 PRD 第一期「Front 硬编码链式、不回流 Agent」一致，属**持久化缺口**而非列表组件渲染故障。

**相关**

- PRD：[student-in-chat-client-actions.md](./prd/student-in-chat-client-actions.md)（创建后链式 list）
- 代码：`appendListStudents`、`submitCreateStudentForm` → `loadHistory` / `historyToDisplayItems`

**候选修复（回头再说）**

- A. Front：`sessionStorage` 按 `thread_id` 缓存链式 `listStudents` 消息，加载历史后合并回放（可 `historical` + 可选重新 GET）。
- B. 契约：创建成功后由 Back/Agent 再记一条 `listStudents` `client_actions`（需改 checkpoint/历史契约，范围更大）。

**备注**

- Agent 直接下发的 `listStudents` 刷新后会出现历史卡片，但一般为只读摘要、不自动拉行数据（109 `historical` 设计）；与本 bug 不同。

---

### BUG-002：无单点登录

| 字段 | 内容 |
|------|------|
| **状态** | open |
| **模块** | `back` 认证（`POST /api/auth/login`、Session Cookie）、`front` `LoginView` / `auth` store |
| **严重程度** | 中（演示可用；对接企业 IdP 前阻塞上线） |

**现象**

- 用户只能通过演示账号 **用户名 + 密码** 登录（`LoginView` → `POST /api/auth/login`）。
- 无法通过企业 IdP（OAuth2/OIDC、SAML 等）**单点登录**；无 SSO 回调、无按 IdP 身份映射 `user_id` / `role_id` 的流程。

**期望**

- 支持企业单点登录：从 IdP 完成认证后建立与现有 Session / `GET /api/me` 一致的登录态，Front 401 仍跳转登录页的逻辑可复用或扩展。

**相关**

- PRD：[demo-admin-console.md](./prd/demo-admin-console.md)（OAuth / SSO 列为非目标，与本条缺口一致）
- 代码：`front/src/views/LoginView.vue`、`front/src/stores/auth.ts`、`front/src/api/auth.ts`

**备注**

- 需产品确认 IdP 类型（OIDC / SAML）、账号绑定规则及是否仍保留本地演示账号。
