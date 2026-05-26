# 88 - 演示平台 Phase 2c：Back context 注入、tools 并集与 chat_threads

## 建议执行模型

- 模型：GPT-5 或同档强编码模型
- Reasoning：medium
- 原因：连接 Session、`role_ids[]`、工具白名单与 Agent 转发；需 thread 归属防 IDOR。

## 新窗口执行规则

1. 先读 PRD 模块五、Context 契约、工具白名单 JSON 示例。
2. 核对 **82**、**86**、**87** 已完成。
3. Front 仍只传 `thread_id` + `message`。

## 依赖

82, 86, 87

## 背景

Back 每轮从 session 组装 `context` 转发 Agent；**禁止**信任 checkpoint 中的 `user_id`/`role_ids`。`chat_threads` 表绑定 `thread_id` → `user_id`，防跨用户读历史。

## 目标

- 扩展 `back/src/services/context.py`：`filter_tools_for_role_ids(role_ids)` 并集去重。
- `POST /api/chat`：校验 thread 属主；首次 chat 登记 `chat_threads`；注入 `user_id`、`role_ids[]`、`tools[]` 转发 Agent SSE。
- 保留现有 demo 转发路径兼容；`role_id` 单字段调用方改为 `role_ids`（内部可 deprecated 映射一版）。
- 环境：`AGENT_URL` 不变。

## 范围

| 模块 | 变更 |
|------|------|
| `back/src/services/context.py` | 多角色 tools |
| `back/src/` chat 路由 | thread 归属、转发 body |
| `back/config/tools.demo.json` | `roles` 数组与 PRD 一致 |
| `back/tests/` | context 并集、thread 403、转发 payload 含 `role_ids` |

## 验证方案

```bash
cd back && uv run pytest tests/test_demo_chat_context.py tests/test_back_forward.py -v
# Agent 可 mock；断言转发 JSON context.role_ids
```

## 非范围

- Front ChatDrawer SSE UI（**91**）
- `GET /api/threads/.../messages`（**91**）
- KB 管理（**89–90**）

## 完成标准

- [ ] 多角色用户 chat 请求中 `role_ids` 为绑定全集。
- [ ] 用户 A 无法访问用户 B 的 `thread_id`（403）。
- [ ] `jumpPage` 等工具仅出现在并集白名单内。
- [ ] progress **88** → `✅`。

## 进度更新

完成后建议下一步 **89** 或 **91**（91 依赖本任务）。
