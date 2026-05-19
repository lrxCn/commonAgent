# 03 - Postgres Checkpointer

## 依赖

01, 02

## 目标

LangGraph 使用 **Postgres Checkpointer** 持久化对话；`thread_id` 为会话维度键。

## 范围

- `agent/src/memory/checkpointer.py`：`get_checkpointer()` 工厂
- docker-compose 或文档说明本地 Postgres（可选 `docker-compose.yml` 在根或 agent）
- 最小集成测试：写入一条 thread 后能 `get_state`

## 非范围

- 分页 API（任务 19）

## 实现要点

- 使用 `langgraph.checkpoint.postgres` 官方适配器
- 连接串来自 `DATABASE_URL`
- 启动时 `checkpointer.setup()`（若库要求）

## 测试方案

```bash
cd agent
# 需本地 Postgres；无则 SKIP 并注明
uv run pytest tests/test_checkpointer.py -v -m "not integration"  # 单元 mock
uv run pytest tests/test_checkpointer.py -v -m integration       # 有 DB 时
```

**通过标准**：integration 测试能 create thread → append → read；无 DB 时单元测试至少验证工厂与配置加载。

## 完成标准

- Checkpointer 可被 graph compile 注入
- README 说明如何起 Postgres

## 进度更新

`docs/progress.md` **03** → `✅`
