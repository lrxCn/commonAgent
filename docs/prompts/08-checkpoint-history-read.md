# 08 - Checkpoint 历史读取

## 依赖

03, 04

## 目标

按 `thread_id` 从 checkpointer 读取消息列表，供 K+M+summary 组装。

## 范围

- `agent/src/memory/history.py`：
  - `load_thread_messages(thread_id) -> list[BaseMessage]`
  - `get_rolling_summary(thread_id) -> str | None`（存 metadata 或独立表字段，第一期可用 checkpoint metadata）
- 不修改 context 中的 user_id/role_id

## 非范围

- 分页 HTTP（19）
- summary 生成（17）

## 实现要点

- 消息顺序与时间戳一致
- 提供 `count_turns(messages)` 辅助

## 测试方案

```bash
cd agent
uv run pytest tests/test_history.py -v
```

integration：写入多轮后 load 条数正确；summary 字段可读。

## 完成标准

- 返回 LangChain message 类型列表
- 空 thread 返回 `[]`

## 进度更新

`docs/progress.md` **08** → `✅`
