# 110 - 对话内学生工具：创建后链式列表、历史回放与文档收口

## 建议执行模型

- 模型：GPT-5 或同档强编码模型
- Reasoning：medium
- 原因：跨 store 链式逻辑与多份文档契约对齐，需核对 106–109 实际落地。

## 新窗口执行规则

1. 先读 `AGENTS.md`、`README.md`、`docs/progress.md` 与本任务卡。
2. 阅读 PRD：[student-in-chat-client-actions.md](../prd/student-in-chat-client-actions.md)。
3. 核对 **106–109** 均已完成；否则停止。
4. 实现 create→list 链式、补全 historical 边界、同步文档。
5. smoke 测试后更新 progress 并 commit。

## 依赖

106, 108, 109

## 背景

第二代学生 client_actions 批次（106–109）完成 Back schema、表单卡片与列表卡片。本任务收口：**创建成功后 Front 自动追加 listStudents**（默认 `{ offset: 0, limit: 10 }`），完善历史回放，并更新 README / maps / demo-walkthrough / PRD 落地状态。

## 目标

- `submitCreateStudentForm` 成功 → `appendListStudents(DEFAULT_LIST_AFTER_CREATE)`（不回流 Agent）。
- 确认 historical 回放：表单/列表均不可提交或翻页。
- 文档对齐第二代语义；删除第一代 createStudent（确认卡片+跳转）描述。
- PRD 落地状态表更新为完成。

## 范围

| 模块 | 变更 |
|------|------|
| `front/src/stores/chat.ts` | `appendListStudents`；create success 钩子 |
| `front/src/client-actions/list-students.ts` | `DEFAULT_LIST_AFTER_CREATE` 常量（若未导出） |
| `README.md` | client_actions 示例：inline createStudent + listStudents |
| `docs/maps/client-actions.md` | 两工具行、删除 student-ui 引用 |
| `docs/demo-walkthrough.md` | 替换 B4b 为对话内表单/列表脚本 |
| `docs/prd/student-in-chat-client-actions.md` | 落地状态 ✅ |
| `docs/progress.md` | 106–110 ✅；总任务 110；changelog |

## 实施步骤

1. 在 create 表单 POST 成功后调用 `appendListStudents({ offset: 0, limit: 10 })`，push 新 list 消息并 fetch。
2. 复查 `historyToDisplayItems` 对 createStudent / listStudents 的 historical 状态。
3. 更新 README `client_actions` 节：移除「确认卡片 / 跳转学生页 / student-ui」描述；增加 listStudents。
4. 更新 `docs/maps/client-actions.md`、`docs/demo-walkthrough.md` B4b。
5. PRD 落地状态表全部 ✅。
6. progress 总览：总任务 110，建议下一步改为手工验收或 backlog。

## 验证方案

```bash
cd back && uv run pytest tests/test_demo_chat_context.py -v
cd agent && uv run pytest tests/test_client_actions.py -v
cd front && npm run build
rg -n "CreateStudentConfirmCard|student-ui|createStudentPrompt|确认打开" README.md docs/ front/src || true
```

手工：

1. 新建学生 → 确定 → 成功 toast → 对话内自动出现列表。
2. 单独「查学生列表」→ 列表可翻页搜索。
3. 重开 drawer 历史：表单/列表 historical。
4. 侧栏 `/app/students` CRUD 仍可用。

## 非范围

- 创建后 list 带 search=新学号（PRD 开放问题：第一期否）
- 列表操作列、对话内编辑删除
- 修改 `AGENTS.md` 治理顺序

## 完成标准

- [ ] create 成功自动 append list（默认第一页）。
- [ ] README / maps / demo-walkthrough / PRD 与代码一致；无第一代描述残留。
- [ ] smoke 测试绿。
- [ ] progress **110** → `✅`；批次 106–110 完成。
- [ ] git commit。

## 进度更新

`docs/progress.md` **110** → `✅`；建议下一步：按 [demo-walkthrough.md](../demo-walkthrough.md) B4b 做端到端验收。
