# 91 - 演示平台 Phase 4a：ChatDrawer 对话（SSE、history、client_actions）

## 建议执行模型

- 模型：GPT-5 或同档强编码模型
- Reasoning：medium
- 原因：迁移现有 static front 的 SSE/client_actions 逻辑到 Vue 组件与 Pinia。

## 新窗口执行规则

1. 先读 PRD 模块五、现有 `front/app.js`（legacy）与 **88** Back chat API。
2. 核对 **88**、**84** 已完成。
3. 关闭 drawer 时实现取简单：**关闭即 abort 当前 SSE**（PRD 允许）。

## 依赖

88, 84

## 背景

对话在全局右侧抽屉；`thread_id` 存 **sessionStorage**（按 tab）；展示当前 `role_ids`（来自 `/api/me`）。历史由 Back 代理 Agent，带 thread 归属校验。

## 目标

- `ChatDrawer`：消息列表、输入、新开 thread（UUID + Back 登记）、可复制 `thread_id`、只读 `role_ids`。
- `stores/chat.ts`：SSE 解析（token/done/client_actions/retract 等，与当前 Agent/Back 契约一致）。
- `client_actions`：console 日志；`requires_approval` → `confirm()`。
- `GET /api/threads/{thread_id}/messages`：进入 thread 或打开 drawer 时拉历史（若 **88** 未实现则本任务一并实现 Back 代理）。

## 范围

| 模块 | 变更 |
|------|------|
| `front/src/components/chat/ChatDrawer.vue` | 完整实现 |
| `front/src/stores/chat.ts` | SSE + thread |
| `front/src/api/chat.ts` | chat + history |
| `back/` | 若缺 history 代理则补齐 |

## 验证方案

```bash
cd back && uv run pytest tests/test_demo_chat_history.py -v
cd front && npm run build
# 手动脚本 B 步骤 2–4：alice/bob 问答、admin client_actions
```

## 非范围

- 删 legacy static（**92**）
- README 大改（**92**）

## 完成标准

- [ ] SSE 流式显示；`client_actions` 可在控制台看到。
- [ ] 跨用户 thread 403；新开 thread 可继续对话。
- [ ] progress **91** → `✅`。

## 进度更新

完成后建议下一步 **92**（文档收口）。
