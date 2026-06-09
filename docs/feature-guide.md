# commonAgent 功能说明文档

本文面向项目使用者、演示人员和交接维护人员，说明当前系统已经具备的功能、入口、权限边界和使用方式。架构细节以根目录 [README.md](../README.md) 为准，逐步演示脚本见 [demo-walkthrough.md](./demo-walkthrough.md)。

## 1. 项目定位

commonAgent 是一个三层通用智能体演示平台：

- **Front**：Vue 3 管理后台，提供登录、学生管理、账号管理、RAG 管理、智能对话、WebRTC 通话和实时字幕。
- **Back**：业务后端，负责 Cookie Session、权限、业务数据、Agent 转发、WebRTC 信令和 ASR 代理。
- **Agent**：内网智能体服务，负责 LangGraph 对话流程、长期记忆、RAG 检索、工具动作生成和安全护栏。

浏览器只访问 Back，不直接访问 Agent。Back 会根据登录用户注入 `user_id`、`role_ids[]` 和可用工具列表。

## 2. 默认账号

本地执行种子后可使用以下账号：

| 用户名 | 密码 | 角色 | 主要权限 |
|--------|------|------|----------|
| `admin` | `123456` | `role-admin` | 学生管理、账号管理、RAG 管理、智能对话、通话 |
| `alice` | `demo123` | `role-sales` | 学生管理、智能对话、通话 |
| `bob` | `demo123` | `role-support` | 学生管理、智能对话、通话 |

访问入口：`http://127.0.0.1:5173`

## 3. 登录与首页

登录页支持账号密码登录，登录成功后进入 `/app/home`。前端通过 HttpOnly Cookie 保持会话，并通过 `GET /api/me` 获取当前用户、角色和管理员状态。

主要行为：

- 未登录访问 `/app/*` 会跳转到 `/login`。
- 登出后清空前端会话和对话 thread 绑定。
- 切换用户登录时会重置当前 `thread_id`，避免串用上一用户对话。

## 4. 学生管理

入口：侧边栏 **学生管理**，路径 `/app/students`。

功能：

- 学生列表查询。
- 新建学生。
- 编辑学生。
- 删除学生。
- 批量删除。
- 按条件搜索和分页。

学生数据由 Back 的 `/api/students` 系列接口维护。当前版本是演示用共享学生表，不做学生行级隔离。

## 5. 智能对话

入口：登录后任意 `/app/*` 页面右下角对话入口。

能力：

- 与 Agent 进行流式对话。
- 自动携带当前用户、角色和工具白名单。
- 支持历史消息加载。
- 支持新会话。
- 支持角色隔离的 RAG 知识库问答。
- 支持长期记忆读写。
- 支持客户端工具动作。

对话链路：

1. Front 调 Back：`POST /api/chat`。
2. Back 读取 Cookie Session，注入 `user_id`、`role_ids[]`、`tools[]`。
3. Back 转发 Agent：`POST /internal/chat`。
4. Agent 返回 SSE 文本流或 `client_actions`。
5. Front 渲染文本或执行客户端动作。

## 6. 对话内工具

Agent 不直接操作浏览器页面和业务数据，而是返回 `client_actions`，由 Front 执行。

当前已支持：

| 工具 | 功能 | 前端表现 |
|------|------|----------|
| `jumpPage` | 页面跳转 | 对话内出现跳转确认卡片，确认后路由跳转 |
| `createStudent` | 新建学生 | 对话内出现学生表单，用户确认后调用 `/api/students` |
| `listStudents` | 查询学生 | 对话内出现学生列表卡片，可展示搜索结果 |

示例话术：

- “打开学生管理”
- “打开 RAG 管理页面”
- “帮我新建一个学生，姓名张三，学号 2024999”
- “查一下学生列表”
- “帮我查找李四的详细信息”

权限说明：

- 普通用户无法跳转到管理员页面。
- Front 会二次校验页面权限，避免 Agent 返回越权页面后直接跳转。
- 学生工具由 Front 调 Back 执行，不由 Agent 直接访问业务库。

## 7. RAG 知识库管理

入口：管理员侧边栏 **RAG 管理**，路径 `/app/admin/kb`。

功能：

- 新建知识库文档。
- 上传或录入 Markdown / TXT 内容。
- 给文档绑定一个或多个角色。
- 查看文档列表、角色标签和详情。
- 编辑文档内容、版本和角色绑定。
- 删除文档。

角色隔离规则：

- 文档使用 `role_ids[]` 绑定可见角色。
- 用户对话时只会检索与自己角色有交集的文档。
- 多角色文档可同时被多个角色检索。
- 仅管理员可管理 KB 文档。

数据分工：

- Back 保存文档元信息、原文和角色绑定。
- Agent 将文档切分后写入 Qdrant。
- Agent 检索时按 `role_ids[]` 做过滤。

## 8. 账号与角色管理

管理员入口：

- **角色管理**：`/app/admin/roles`
- **用户管理**：`/app/admin/users`

角色管理功能：

- 查看角色。
- 新建角色。
- 编辑角色。
- 删除角色。

用户管理功能：

- 查看用户。
- 新建用户。
- 编辑用户信息。
- 绑定多个角色。
- 重置或设置密码。
- 删除用户。

管理员身份由 `role-admin` 推导。普通用户无法访问管理员路由和管理员 API。

## 9. WebRTC 账号通话

入口：侧边栏 **通话**，路径 `/app/calls`。

功能：

- 查看可呼叫用户。
- 发起 1 对 1 语音呼叫。
- 被叫方在任意应用页面左下角收到来电条。
- 支持接听、拒接、取消和挂断。
- 通话中显示状态和计时。

技术边界：

- Back 只负责 WebSocket 信令中继。
- 音频媒体通过浏览器 `RTCPeerConnection` 点对点传输。
- Agent 不参与通话。
- 当前信令 hub 是单进程内存实现，多 worker 部署需要改造。

## 10. 通话实时字幕

入口：通话接通后在 `/app/calls` 页面显示字幕区域。

功能：

- 采集本地麦克风音频和远端音频。
- 分为 `local` / `remote` 双轨识别。
- 识别结果按“我说 / 对方说”展示。
- 挂断后在浏览器控制台输出分角色 transcript。
- ASR 失败不会影响 WebRTC 通话本身。

当前 ASR 支持：

- 火山 SAUC 实时 ASR。
- 科大讯飞 iat WebSocket ASR。
- STT 文件转写配置仅作为 fallback 配置，不作为实时通话字幕主路径。

凭证要求：

- ASR 凭证只放在 `back/.env`。
- 不应放入 `front/.env` 的 `VITE_*` 变量中，因为前端变量会暴露给浏览器。

## 11. 长期记忆

Agent 支持用户长期记忆：

- 结构化 Profile：如姓名、城市、公司、偏好等。
- 自由文本记忆：通过 langmem 抽取和 Store 保存。
- 记忆查询：用户问“你记得我叫什么吗”这类问题时可走 memory_query 快路径。
- 事实写入：用户表达稳定事实时可通过策略门控写入。

记忆存储使用 LangGraph Postgres Store 和 langmem，不使用第三方托管记忆 SaaS。

## 12. Agent 对话流程能力

Agent 内部基于 LangGraph，主要能力包括：

- 入站护栏。
- 意图分类。
- 事实写入判断。
- 记忆查询。
- Query Rewrite。
- RAG 路由。
- Qdrant 检索。
- 上下文组装。
- Supervisor 回复。
- 客户端动作生成。
- 出站护栏。
- 异步 summary 和记忆写入。

这些能力对前端用户表现为：能聊天、能查知识库、能记住用户事实、能触发页面跳转和业务卡片。

## 13. 权限边界

核心规则：

- 浏览器只访问 Back，不直连 Agent。
- Back 拥有登录态、角色计算和工具白名单过滤权。
- Agent 只接收 Back 注入的 `user_id`、`role_ids[]`、`tools[]`。
- Agent 不可信任 checkpoint 中残留的权限字段。
- 外部工具只通过 `client_actions` 发给 Front 执行。
- Front 负责 `thread_id`、页面跳转确认和客户端动作执行。
- 管理员页面和 API 需要 admin 权限。

## 14. 本地运行入口

推荐使用根目录脚本：

```bash
./dev.sh up
```

常用命令：

| 命令 | 说明 |
|------|------|
| `./dev.sh up` | 启动 Postgres、Qdrant、Agent、Back、Front |
| `./dev.sh status` | 查看服务状态 |
| `./dev.sh logs back` | 查看 Back 日志 |
| `./dev.sh logs agent` | 查看 Agent 日志 |
| `./dev.sh logs front` | 查看 Front 日志 |
| `./dev.sh down` | 停止应用服务 |

默认端口：

| 服务 | 地址 |
|------|------|
| Front | `http://127.0.0.1:5173` |
| Back | `http://127.0.0.1:8080` |
| Agent | `http://127.0.0.1:18080` |
| Qdrant | `http://127.0.0.1:6333` |
| Postgres | `127.0.0.1:5432` |

手动启动方式见 [README.md](../README.md#本地运行)。

## 15. 常用演示路径

### 学生管理演示

1. 使用 `alice / demo123` 登录。
2. 进入学生管理。
3. 新建一个学生。
4. 搜索或编辑该学生。
5. 打开智能对话，发送“查一下学生列表”。

### RAG 角色隔离演示

1. 使用 `admin / 123456` 登录。
2. 进入 RAG 管理。
3. 创建 sales 文档、support 文档和共享文档。
4. 使用 `alice` 询问 sales 知识。
5. 使用 `bob` 询问 support 知识。
6. 验证不同角色只能命中对应文档。

### 对话工具演示

1. 打开智能对话。
2. 发送“打开学生管理”。
3. 确认跳转卡片。
4. 发送“帮我新建一个学生，姓名张三，学号 2024999”。
5. 在对话内确认表单。
6. 查看自动追加的学生列表卡片。

### 通话与字幕演示

1. 两个浏览器分别登录 `alice` 和 `bob`。
2. `alice` 在通话页呼叫 `bob`。
3. `bob` 在来电条点击接听。
4. 双方说话，观察实时字幕。
5. 挂断后查看浏览器控制台 transcript。

## 16. 当前未完成或限制

当前已知限制：

- 通话转写持久化任务 124-127 尚未完成，挂断 transcript 当前主要输出在浏览器控制台。
- WebRTC 信令和 ASR 会话是单进程内存实现，多 worker / 多实例部署需要外部状态或消息总线。
- 学生表是演示共享数据，未做行级隔离。
- OAuth、单点登录、PDF 知识库上传等 PRD 二期项未实现。
- ASR 凭证、LLM 凭证、数据库密码等需要本地 `.env` 配置，不能提交到 git。

## 17. 故障排查入口

常见问题可先查看：

- [demo-walkthrough.md](./demo-walkthrough.md#故障排查)
- 根目录 `.dev/back.log`
- 根目录 `.dev/agent.log`
- 根目录 `.dev/front.log`

常用检查：

```bash
./dev.sh status
curl http://127.0.0.1:8080/health
curl http://127.0.0.1:18080/health
```

测试入口：

```bash
cd back && uv run pytest tests/test_demo_auth.py tests/test_demo_students.py tests/test_call_signaling.py tests/test_asr_ws.py -v
cd front && npm run build
cd agent && uv run pytest tests/test_schemas.py tests/test_role_ids_filter.py -v
```
