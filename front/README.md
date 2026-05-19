# Front（占位）

最小对话页：`thread_id` 存在 **sessionStorage**；仅请求 **Back**（不直连 Agent）；展示 SSE 文本流；`client_actions` 输出到浏览器 **Console**（`requires_approval=true` 时先 `confirm()`）。

## 启动顺序

1. **Agent**（内网 Gateway）  
2. **Back**（须开启 CORS，见 `back/src/api/app.py`）  
3. **Front**（本目录）

```bash
# 终端 1 — Agent
cd agent && uv sync && uv run uvicorn main:app --host 127.0.0.1 --port 18080

# 终端 2 — Back
cd back && uv sync && uv run uvicorn main:app --host 127.0.0.1 --port 8080

# 终端 3 — Front
cd front && npm run start
# 浏览器打开 http://127.0.0.1:3000
```

页面上的 **Back URL** 默认 `http://127.0.0.1:8080`，可按环境修改。

## 手动测试步骤

1. 打开 http://127.0.0.1:3000 ，确认页头显示 `thread_id`（首次访问会自动 `crypto.randomUUID()` 并写入 sessionStorage）。
2. 打开 DevTools → **Network** 与 **Console**。
3. 发送「你好」：
   - Network：`POST /api/chat` 状态 200，`Content-Type` 为 `text/event-stream`；
   - 页面助手区逐字出现回复。
4. 发送「请跳转到 pageA」或类似意图（触发 `jumpPage`）：
   - 若 Back 返回 JSON（含 `client_actions`），Console 出现 `[client_actions]` 日志；
   - 若工具 `requires_approval: true`，应先弹出确认框再 log。
5. 点击「新开 thread」：生成新 `thread_id`、清空对话区；改权限/上传文档场景请用此操作（文案提示，逻辑后期实现）。

刷新页面后 `thread_id` 应保持不变（sessionStorage）。

## 历史消息

任务 22 Back **未**代理 Agent 历史 API，故本占位 **无**「拉取历史」按钮。后续 Back 增加 `GET /api/threads/{id}/messages` 代理后可再接。

## 文件

| 文件 | 说明 |
|------|------|
| `index.html` | 单页结构 |
| `app.js` | chat / SSE / client_actions |
| `styles.css` | 最小样式 |

任务卡：[docs/prompts/23-front-stub.md](../docs/prompts/23-front-stub.md)
