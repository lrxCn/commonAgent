# Client Actions

回答的问题：`client_actions` 从哪里生成，谁做白名单，为什么不在 Agent 内执行。

## 边界

- 请求契约在 [schemas.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/gateway/schemas.py:1)。
- Back 在 [context.py](/Users/liurixing/Documents/codes/ai/commonAgent/back/src/services/context.py:1) 注入 `tools[]` 白名单。
- Agent 只把动作表达成 `ClientAction`；Front 才是真正执行者。

## 生成路径

1. Back 把允许工具塞入 `context.tools`。
2. [engine.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/intent/engine.py:1) / 兼容 `turn_type` / executor router 识别动作意图。
3. 简单动作可由 [executors.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/graph/executors.py:1) 构造；复杂动作可由 deepagents 输出结构化 JSON。
4. Agent 在 [client_actions.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/graph/client_actions.py:1) 解析模型输出并校验是否在白名单内。
5. 图进入 `client_actions_emit` 节点，落到 `state.client_actions`。
6. Gateway 在 [chat.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/gateway/chat.py:1) 检测到 `client_actions` 后返回 JSON。

## 为什么不在 Agent 内执行

- 外部工具属于客户端能力，不在 LangChain/deepagents 注册表中。
- Agent 不等待结果，不生成 ToolMessage，不 resume。
- 浏览器直连 Agent 被禁止；Front -> Back -> Agent 边界保持单向。

## 运行规则

- `requires_approval` 来自 Back 传入的工具定义，Agent 原样返回给 Front。
- 动作准入由 Back 白名单、intent route、executor router、参数构造和 schema 解析共同约束。
- 工具不可用、未授权、参数不可构造或 schema invalid 时，Agent 返回用户可见 fallback，不执行工具。
- 带 `tools[]` 的回合禁用 live token streaming，避免 JSON 被拆成 token。
- `client_actions` 回合跳过 outbound 文本护栏，直接走结构化返回。

## Front 执行（jumpPage / createStudent / listStudents）

演示平台外部工具：**`jumpPage`**、**`createStudent`**、**`listStudents`**（早期 `openTicket` 占位已移除，见 [jumpPage-client-action.md](../prd/jumpPage-client-action.md) 与 [student-in-chat-client-actions.md](../prd/student-in-chat-client-actions.md)）。

| 层 | 入口 | 职责 |
|----|------|------|
| Back | [tools.demo.json](/Users/liurixing/Documents/codes/ai/commonAgent/back/config/tools.demo.json) | 三工具 schema；按 `role_ids[]` 并集注入白名单 |
| Agent | [jump_page_catalog.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/graph/jump_page_catalog.py) | jumpPage 规则路径 slug/中文/path 抽取（非 prompt 权威源） |
| Front | [page-registry.ts](/Users/liurixing/Documents/codes/ai/commonAgent/front/src/client-actions/page-registry.ts) | jumpPage：slug → Vue route name；admin 页权限校验 |
| Front | [create-student.ts](/Users/liurixing/Documents/codes/ai/commonAgent/front/src/client-actions/create-student.ts) | createStudent：参数校验/清洗、预填 |
| Front | [list-students.ts](/Users/liurixing/Documents/codes/ai/commonAgent/front/src/client-actions/list-students.ts) | listStudents：参数校验；`DEFAULT_LIST_AFTER_CREATE` |
| Front | [stores/chat.ts](/Users/liurixing/Documents/codes/ai/commonAgent/front/src/stores/chat.ts) | `handleClientActions`：jumpPage 确认跳转；create/list 对话内嵌 UI；create 成功 `appendListStudents` |
| Front | [CreateStudentFormCard.vue](/Users/liurixing/Documents/codes/ai/commonAgent/front/src/components/chat/CreateStudentFormCard.vue) | 对话内新建表单 |
| Front | [StudentListCard.vue](/Users/liurixing/Documents/codes/ai/commonAgent/front/src/components/chat/StudentListCard.vue) | 对话内列表（翻页/搜索；历史 `historical` 只读） |

slug catalog（Back enum 与 Front registry 手动同步）：

| `page` slug | 菜单 | route name |
|-------------|------|------------|
| `home` | 首页 | `app-home` |
| `students` | 学生管理 | `app-students` |
| `admin-roles` | 角色管理（admin） | `app-admin-roles` |
| `admin-users` | 用户管理（admin） | `app-admin-users` |
| `admin-kb` | RAG 管理（admin） | `app-admin-kb` |

**createStudent**（`role-admin` / `role-sales`）：收到 action 即渲染表单；用户点确定 POST `/api/students`；成功 toast 后 Front 自动追加 `listStudents`（默认第一页），不回流 Agent。

**listStudents**：收到 action 或 create 链式追加后 GET `/api/students`；对话内翻页/搜索；历史回放为 `historical`，无行数据时展示查询摘要。

## 实现入口

- 契约：[schemas.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/gateway/schemas.py:1)
- 动作解析：[client_actions.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/graph/client_actions.py:1)
- Executor routing：[executors.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/graph/executors.py:1)
- Tool fallback：[fallback.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/intent/fallback.py:1)
- Gateway 输出：[chat.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/src/gateway/chat.py:1)
- Back 白名单与转发：[context.py](/Users/liurixing/Documents/codes/ai/commonAgent/back/src/services/context.py:1)、[forward.py](/Users/liurixing/Documents/codes/ai/commonAgent/back/src/services/forward.py:1)
- Front 执行：[page-registry.ts](/Users/liurixing/Documents/codes/ai/commonAgent/front/src/client-actions/page-registry.ts:1)、[create-student.ts](/Users/liurixing/Documents/codes/ai/commonAgent/front/src/client-actions/create-student.ts:1)、[list-students.ts](/Users/liurixing/Documents/codes/ai/commonAgent/front/src/client-actions/list-students.ts:1)、[stores/chat.ts](/Users/liurixing/Documents/codes/ai/commonAgent/front/src/stores/chat.ts:1)

## 测试入口

- 动作解析与白名单：[test_client_actions.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_client_actions.py:1)
- 工具 fallback：[test_fallback_manager.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_fallback_manager.py:1)
- SSE/JSON 输出分流：[test_chat_sse.py](/Users/liurixing/Documents/codes/ai/commonAgent/agent/tests/test_chat_sse.py:1)
- Back 转发：[test_back_forward.py](/Users/liurixing/Documents/codes/ai/commonAgent/back/tests/test_back_forward.py:1)
- Back 演示白名单：[test_demo_chat_context.py](/Users/liurixing/Documents/codes/ai/commonAgent/back/tests/test_demo_chat_context.py:1)
