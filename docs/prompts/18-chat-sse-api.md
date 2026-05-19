# 18 - Chat SSE API

## 依赖

05, 13, 15, 16

## 目标

`POST /internal/chat` 真实调用图：文本回复走 **SSE**；`client_actions` 走 JSON 一次返回。

## 范围

- `agent/src/gateway/chat.py`：StreamingResponse
- 事件格式：`data: {"type":"token","content":"..."}` 与 `data: {"type":"done"}`；client_actions 时 `type: client_actions`
- 入站护栏失败 400；出站失败安全消息

## 非范围

- Back 转发

## 实现要点

- thread_id 传入 `configurable`
- 首 token 前完成：并行读、rewrite、RAG（可跳过）

## 测试方案

```bash
cd agent
uv run pytest tests/test_chat_sse.py -v
# integration
curl -N -X POST http://127.0.0.1:18080/internal/chat \
  -H 'Content-Type: application/json' \
  -d '{"thread_id":"t1","message":"hi","context":{"user_id":"u1","role_id":"r1","tools":[]}}'
```

断言：响应 `text/event-stream` 或 JSON 含 client_actions。

## 完成标准

- 与 architecture §8.1 一致
- mock 图下 SSE 至少 1 个 token 事件

## 进度更新

`docs/progress.md` **18** → `✅`
