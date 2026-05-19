# 19 - 历史分页 API

## 依赖

03, 05, 08

## 目标

`GET /internal/threads/{thread_id}/messages` 分页返回对话历史，与 checkpoint **同源**。

## 范围

- `agent/src/gateway/history.py`
- 查询参数：`cursor`（offset 或 message_id）、`limit`（默认 20，max 100）
- 响应：`{ "items": [...], "next_cursor": "..." }`
- 每条含 role、content、timestamp、可选 `client_actions` metadata

## 非范围

- 独立 UI messages 表

## 实现要点

- 只读 checkpointer
- 不用于模型推理，仅供 Back/Front 展示

## 测试方案

```bash
cd agent
uv run pytest tests/test_history_api.py -v
```

写入 25 条后 limit=10 分页两次 cursor 不重复。

## 完成标准

- OpenAPI 文档含该路由
- 空 thread 返回空 items

## 进度更新

`docs/progress.md` **19** → `✅`
