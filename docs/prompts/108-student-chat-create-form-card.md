# 108 - 对话内学生工具：CreateStudentFormCard 与 createStudent 执行

## 建议执行模型

- 模型：GPT-5 或同档强编码模型
- Reasoning：medium
- 原因：表单 UI + chat store 状态机 + API 提交，需处理 loading/error/success。

## 新窗口执行规则

1. 先读 `AGENTS.md`、`README.md`、`docs/progress.md` 与本任务卡。
2. 阅读 PRD：[student-in-chat-client-actions.md](../prd/student-in-chat-client-actions.md)。
3. 核对 **107** 已完成。
4. 只实现 createStudent 对话内表单流；listStudents 与创建后链式刷新留给 **109/110**。
5. 测试通过后更新 progress 并 commit。

## 依赖

107

## 背景

Agent 产出 `createStudent` 后，Front 应**立即**在 ChatDrawer 消息流展示可编辑表单（无执行前确认卡片）。用户点「确定」调用 `POST /api/students`；成功后在卡片内展示已创建摘要。

## 目标

- 新建 `CreateStudentFormCard.vue`：学号/姓名/班级/状态；确定/取消；复用 `create-student.ts` 预填逻辑。
- `chat.ts`：`enqueueCreateStudentForm`、`submitCreateStudentForm`、`cancelCreateStudentForm`；`handleClientActions` 接入 `createStudent`。
- `ChatDrawer.vue` 渲染 `msg.createStudentForm`。
- 历史消息中 createStudent action 回放为 `historical` 只读表单。

## 范围

| 模块 | 变更 |
|------|------|
| `front/src/components/chat/CreateStudentFormCard.vue` | 新建 |
| `front/src/stores/chat.ts` | createStudent 表单 enqueue/submit/cancel |
| `front/src/components/chat/ChatDrawer.vue` | 挂载 FormCard |
| `front/src/types/index.ts` | 若缺 `cancelled` 状态则按 PRD 补充 |

## 实施步骤

1. 实现 `CreateStudentFormCard.vue`：
   - props：`prefill`、`status`、`errorDetail`、`createdStudent`
   - emit：`submit(payload)`、`cancel`
   - 状态：`editable` / `submitting` / `success` / `error` / `cancelled` / `historical`
2. `enqueueCreateStudentForm(action)`：validate → push message with `createStudentForm: { prefill, status: 'editable' }`。
3. `submitCreateStudentForm(messageId)`：调 `api/students.ts` `createStudent`；成功 → `status: success` + 存 `createdStudent`；失败 → `error` + field_errors 展示。
4. `cancelCreateStudentForm` → `status: cancelled`，禁用表单。
5. `historyToDisplayItems`：createStudent → historical 表单消息。
6. 更新 ChatDrawer 空状态提示文案（可选）。

## 验证方案

```bash
cd front && npm run build
```

手工（需 Back 运行）：

1. 对话发送触发 createStudent（或 mock `handleClientActions`）→ 对话内出现表单，无确认卡片。
2. 预填字段正确；空 args 时表单为空。
3. 确定 → POST 成功 → 卡片 success；取消 → cancelled。
4. 历史回放为 historical。

## 非范围

- `StudentListCard` / `listStudents`（**109**）
- create 成功后自动 list（**110**）
- Back `tools.demo.json`（**106** 已完成）

## 完成标准

- [ ] createStudent 在对话内展示表单并可直接提交。
- [ ] 无第一代确认卡片/跳转逻辑残留。
- [ ] `npm run build` 绿。
- [ ] progress **108** → `✅`。
- [ ] git commit。

## 进度更新

`docs/progress.md` **108** → `✅`；建议下一步 **109**。
