# 106 - 对话内学生工具：Back schema 与 Agent 白名单测试

## 建议执行模型

- 模型：GPT-5 或同档强编码模型
- Reasoning：low
- 原因：配置与测试更新为主，契约已在 PRD 中定稿。

## 新窗口执行规则

1. 先读根目录 `AGENTS.md`、`README.md`、`docs/progress.md` 与本任务卡。
2. 阅读 PRD：[student-in-chat-client-actions.md](../prd/student-in-chat-client-actions.md)。
3. 核对 **105** 已完成；本批次 **106** 无其它依赖。
4. 只实现 Back 工具配置与 Agent/Back 相关测试；不改 Front。
5. 测试通过后更新 `docs/progress.md` **106** → `✅`。
6. 自动 git commit；不 push。

## 依赖

105

## 背景

第一代 `createStudent` 语义为「跳转业务页 + 抽屉预填 + 确认卡片」。第二代 PRD 将其改为「对话内嵌表单」，并新增 `listStudents`。本任务先更新 Back 工具白名单与 ToolSpec，使 Agent 每轮 prompt 可见新契约。

## 目标

- 修订 `createStudent`：`description` 改为 inline form 语义；`requires_approval: false`。
- 新增 `listStudents` 工具定义（`offset/limit/search/status/class_name`，均可选）。
- Back 与 Agent 测试同步新工具名与白名单。

## 范围

| 模块 | 变更 |
|------|------|
| `back/config/tools.demo.json` | 修订 createStudent；新增 listStudents |
| `back/tests/test_demo_chat_context.py` | `_sample_tools()`、白名单断言含三工具 |
| `agent/tests/test_client_actions.py` | `_LIST_STUDENTS_TOOL`；解析空 args / 带 search+offset |

## 实施步骤

1. 按 PRD JSON 示例更新 `createStudent`（`requires_approval: false`，description 强调用户于对话内提交）。
2. 新增 `listStudents` 条目（`requires_approval: false`，`roles` 与 jumpPage 一致）。
3. 更新 `test_demo_chat_context.py`：工具列表为 `jumpPage`、`createStudent`、`listStudents`；`test_demo_tools_file_has_roles_arrays` 断言 listStudents parameters。
4. 在 `test_client_actions.py` 增加 `listStudents` 解析用例；确认 `requires_approval` 来自 ToolSpec 覆盖。

## 验证方案

```bash
cd back && uv run pytest tests/test_demo_chat_context.py -v
cd agent && uv run pytest tests/test_client_actions.py -v
```

## 非范围

- Front 组件与 chat store（**107–109**）
- `rag/router.py` 纯 client 意图扩展（可选，**110** 或后续）
- README / demo-walkthrough 最终对齐（**110**）

## 完成标准

- [ ] `tools.demo.json` 含 jumpPage、createStudent（修订）、listStudents（新增）。
- [ ] Back / Agent 相关测试绿。
- [ ] progress **106** → `✅`。
- [ ] git commit。

## 进度更新

`docs/progress.md` **106** → `✅`；建议下一步 **107**。
