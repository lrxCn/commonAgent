# 107 - 对话内学生工具：Front 类型、校验与第一代链路拆除

## 建议执行模型

- 模型：GPT-5 或同档强编码模型
- Reasoning：medium
- 原因：跨多文件删除旧链路并引入新类型，需避免遗漏引用导致 build 失败。

## 新窗口执行规则

1. 先读 `AGENTS.md`、`README.md`、`docs/progress.md` 与本任务卡。
2. 阅读 PRD：[student-in-chat-client-actions.md](../prd/student-in-chat-client-actions.md)。
3. 核对 **106** 已完成。
4. 只实现本任务范围；**108** 负责 CreateStudentFormCard 与 createStudent 新执行路径。
5. `npm run build` 必须通过（删除旧 UI 引用后，createStudent 可暂不在 ChatDrawer 渲染，或保留占位注释）。
6. 测试通过后更新 progress 并 commit。

## 依赖

106

## 背景

第一代 createStudent 使用 `CreateStudentConfirmCard`、`studentUiStore`、`StudentsView.pendingCreate` 跨页传意图。第二代改为对话内嵌组件，需先拆除旧链路并建立新类型与 listStudents 校验模块。

## 目标

- 新增 `CreateStudentFormMessage`、`ListStudentsMessage` 类型；删除 `CreateStudentPrompt` / `createStudentPrompt`。
- 新增 `front/src/client-actions/list-students.ts`（sanitize/validate/default offset=0 limit=10）。
- 删除第一代文件与引用：`CreateStudentConfirmCard.vue`、`student-ui.ts`。
- 清理 `StudentsView.vue` 中 `pendingCreate` / `consumePendingCreateIntent` / Agent 联动；保留页面自身 CRUD。
- 清理 `chat.ts` 中第一代 createStudent 函数（confirm/execute/navigate/enqueueCreateStudentPrompt 等）；`handleClientActions` 对 `createStudent`/`listStudents` 暂可 no-op 或 DEV console（**108/109** 接入 UI）。

## 范围

| 模块 | 变更 |
|------|------|
| `front/src/types/index.ts` | 新消息类型；删旧 Prompt 类型 |
| `front/src/client-actions/list-students.ts` | 新建 |
| `front/src/client-actions/create-student.ts` | 保留 sanitize/validate（按需微调） |
| `front/src/components/chat/CreateStudentConfirmCard.vue` | 删除 |
| `front/src/stores/student-ui.ts` | 删除 |
| `front/src/stores/chat.ts` | 移除第一代 createStudent 逻辑；history 回放暂不对 create/list 渲染（**110** 补 historical） |
| `front/src/components/chat/ChatDrawer.vue` | 移除 CreateStudentConfirmCard 分支 |
| `front/src/views/StudentsView.vue` | 移除 studentUi import 与 pending watcher |

## 实施步骤

1. 在 `types/index.ts` 按 PRD 添加 `CreateStudentFormMessage`、`ListStudentsMessage` 及 `ChatDisplayMessage` 字段。
2. 实现 `list-students.ts`：`sanitizeListStudentsArgs`、`validateListStudentsAction`、export `DEFAULT_LIST_AFTER_CREATE = { offset: 0, limit: 10 }`。
3. 删除 `CreateStudentConfirmCard.vue`、`student-ui.ts`；`rg` 清理所有引用。
4. 精简 `StudentsView.vue`：`openCreate` 恢复为本地 `resetForm + drawerVisible`（去掉 `openCreateWithPrefill` 的 Agent 入口若仅用于旧链路）。
5. 精简 `chat.ts`：删除 confirm/execute/enqueue 第一代代码；`handleClientActions` 保留 tool 分支骨架供 108/109 填充。
6. `ChatDrawer.vue` 移除 confirm 卡片 import 与模板分支。

## 验证方案

```bash
cd front && npm run build
rg -n "CreateStudentConfirmCard|student-ui|createStudentPrompt|studentUiStore" front/src || true
```

可选单测（若新增 `list-students.test.ts` 或在现有 vitest 中）：

```bash
# 如有 vitest 配置则运行 sanitize 单测；否则 build 即可
cd front && npm run build
```

## 非范围

- `CreateStudentFormCard.vue` / `StudentListCard.vue`（**108/109**）
- create 成功链式 list（**110**）
- README 最终契约（**110**）

## 完成标准

- [ ] 第一代 confirm/store/跨页意图代码已移除；`rg` 无残留引用。
- [ ] 新类型与 `list-students.ts` 就位。
- [ ] `npm run build` 绿。
- [ ] progress **107** → `✅`。
- [ ] git commit。

## 进度更新

`docs/progress.md` **107** → `✅`；建议下一步 **108**（可与 **109** 并行前需完成 107）。
