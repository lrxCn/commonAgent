# 17 - 异步 Summary + mem0 写入

## 依赖

08, 13

## 目标

回复发送后 **异步**：增量更新滚动 summary；**提取式**事实写入 mem0。

## 范围

- `agent/src/memory/summary_job.py`：`update_rolling_summary(thread_id, new_messages, k, m)`
- `agent/src/memory/mem0_write.py`：`extract_and_store(user_id, turn_messages)` — 提取 prompt，非全文
- 使用后台任务（asyncio.create_task / Celery 占位 / FastAPI BackgroundTasks）
- 失败打日志，不阻塞用户

## 非范围

- 用户删记忆 API

## 实现要点

- summary 只处理「上次总结之后」的新消息
- mem0 写入与任务 **07** 相同：**仅本地 `Memory` + Qdrant**，禁止 `MemoryClient` / 云端


## 测试方案

```bash
cd agent
uv run pytest tests/test_summary_job.py tests/test_mem0_write.py -v
```

mock：调用后 summary 变长；mem0 write 被调用且 payload 非完整 transcript。

## 完成标准

- chat 主路径不 await 这些 job（或仅 fire-and-forget）
- 单测覆盖增量逻辑

## 进度更新

`docs/progress.md` **17** → `✅`
