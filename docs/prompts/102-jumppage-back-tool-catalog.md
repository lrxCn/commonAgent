# 102 - jumpPage：Back 工具目录与 openTicket 移除

## 建议执行模型

- 模型：GPT-5 或同档强编码模型
- Reasoning：low
- 原因：配置与测试更新为主，范围窄、契约明确。

## 新窗口执行规则

1. 先读根目录 `AGENTS.md`、`README.md`、`docs/progress.md` 与本任务卡。
2. 阅读 PRD：[jumpPage-client-action.md](../prd/jumpPage-client-action.md)。
3. 核对 **101** 已完成；本批次 **102** 无其它依赖。
4. 只实现 Back 工具配置与相关测试；不改 Agent/Front。
5. 测试通过后更新 `docs/progress.md` **102** → `✅`。
6. 自动 git commit；不 push。

## 依赖

101

## 背景

`jumpPage` 是演示平台唯一保留的前端工具。当前 `back/config/tools.demo.json` 仍含应删除的 `openTicket`，且 `jumpPage` 的 `description` / `parameters` 未列出真实页面 slug，导致 Agent prompt 无法约束 `page` 枚举。

## 目标

- 更新 `jumpPage` 工具定义：`description` 含 slug 与中文菜单对照；`parameters.page.enum` 为 PRD 五档 catalog。
- **删除** `openTicket` 条目。
- Back 测试与 `_sample_tools()`  fixture 同步；openTicket 相关断言移除或改为仅 `jumpPage`。

## 范围

| 模块 | 变更 |
|------|------|
| `back/config/tools.demo.json` | jumpPage catalog enum；删 openTicket |
| `back/tests/test_demo_chat_context.py` | `_sample_tools()`、filter/build 断言 |
| 其它 Back 测试 | 若硬编码 openTicket 则一并清理（`rg openTicket back/`） |

## 实施步骤

1. 按 PRD 示例更新 `jumpPage`（enum：`home`、`students`、`admin-roles`、`admin-users`、`admin-kb`）。
2. 删除 `openTicket`。
3. 更新 `test_demo_chat_context.py`：并集测试改为单工具或仅 jumpPage 场景；support 角色无 jumpPage 的用例可保留（bob 无工具或空 tools）。
4. `rg openTicket back/` 确保无残留。

## 验证方案

```bash
cd back && uv run pytest tests/test_demo_chat_context.py tests/test_back_forward.py -v
rg -n "openTicket" back/
```

## 非范围

- Agent eval / `build_simple_client_action`（**103**）
- Front 路由执行（**104**）
- README / demo-walkthrough（**105**）

## 完成标准

- [ ] `tools.demo.json` 仅含 `jumpPage`，enum 与 PRD 一致。
- [ ] Back 测试绿；仓库 `back/` 无 `openTicket` 引用。
- [ ] progress **102** → `✅`。
- [ ] git commit。

## 进度更新

`docs/progress.md` **102** → `✅`；建议下一步 **103**。
