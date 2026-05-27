# 109 - 对话内学生工具：StudentListCard 与 listStudents 执行

## 建议执行模型

- 模型：GPT-5 或同档强编码模型
- Reasoning：medium
- 原因：表格 + 分页 + 搜索本地状态与 API 联动，组件与 store 协作较多。

## 新窗口执行规则

1. 先读 `AGENTS.md`、`README.md`、`docs/progress.md` 与本任务卡。
2. 阅读 PRD：[student-in-chat-client-actions.md](../prd/student-in-chat-client-actions.md)。
3. 核对 **107** 已完成（**108** 可与本任务并行，但 **110** 依赖两者均完成）。
4. 只实现 listStudents 对话内列表；create 后链式 list 留给 **110**。
5. 测试通过后更新 progress 并 commit。

## 依赖

107

## 背景

用户可通过 Agent 触发 `listStudents`，在对话内查看学生表格，并本地翻页/搜索（直接 `GET /api/students`，不回流 Agent）。列表**无操作列**。

## 目标

- 新建 `StudentListCard.vue`：搜索、状态筛选（可选）、`NDataTable`、分页；列：学号、姓名、班级、状态。
- `chat.ts`：`enqueueListStudents`、`refreshListStudents`；首次 enqueue 后 `loading` → fetch → `ready`。
- `handleClientActions` 接入 `listStudents`。
- `ChatDrawer.vue` 渲染 `msg.listStudents`。
- 历史回放 `historical` 只读。

## 范围

| 模块 | 变更 |
|------|------|
| `front/src/components/chat/StudentListCard.vue` | 新建 |
| `front/src/stores/chat.ts` | listStudents enqueue/refresh |
| `front/src/components/chat/ChatDrawer.vue` | 挂载 ListCard |
| `front/src/client-actions/list-students.ts` | 若 107 未 export 常量则补全 |

## 实施步骤

1. 实现 `StudentListCard.vue`：
   - 展示 `query`、`data`、`status`
   - 搜索/翻页 emit → store `refreshListStudents(messageId, newQuery)`
   - `historical` 禁用交互
2. `enqueueListStudents(action)`：validate/sanitize args → push `{ listStudents: { query, status: 'loading' } }` → 立即 fetch。
3. `refreshListStudents(messageId, query)`：更新 query → loading → `fetchStudents` → ready/error。
4. `historyToDisplayItems`：listStudents → historical + 快照 data（若历史 API 无 data 则仅展示 query 摘要）。
5. ChatDrawer 分支渲染 ListCard。

## 验证方案

```bash
cd front && npm run build
```

手工：

1. Agent 或 mock 触发 `listStudents` → 对话内表格 + 分页。
2. 改搜索/翻页 → 仅 Front 调 API，表格刷新。
3. 无编辑/删除操作列。
4. 历史卡片只读。

## 非范围

- create 成功自动 append list（**110**）
- 对话内编辑/删除学生
- Agent RAG skip 规则（可选后续）

## 完成标准

- [ ] listStudents 在对话内可展示、搜索、翻页。
- [ ] `npm run build` 绿。
- [ ] progress **109** → `✅`。
- [ ] git commit。

## 进度更新

`docs/progress.md` **109** → `✅`；建议下一步 **110**。
