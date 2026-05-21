# 30 - fact_update 快速路径

## 建议执行模型

- 模型：GPT-5.5
- Reasoning：high
- 原因：会改变图路径并跳过 rewrite/RAG/Supervisor，需要保证模板回复、mem0 写入失败和 trace 都可验收。

## 依赖

28, 29

## 背景

`fact_update` 如「我出生于1997年」「我生活在哈尔滨」不需要 rewrite、RAG、Supervisor。应直接模板确认，并异步写 mem0。

## 目标

- `fact_update` 走快速路径。
- 不调用 rewrite/router/RAG/Supervisor LLM。
- 当前 human 与模板 assistant 仍进入 checkpoint。
- post_turn 异步写 mem0；失败可观测但不阻塞本轮。

## 范围

| 模块 | 变更 |
|------|------|
| `agent/src/graph/build.py` / `nodes.py` | 增加 fact_update 路由分支 |
| `agent/src/graph/nodes.py` | 新增模板确认节点 |
| `agent/src/memory/post_turn.py` | 确保 fast path 也调度 mem0 写入 |
| `agent/src/observability/tracing.py` | 记录 `fast_path=true`、mem0 写入调度状态 |
| `agent/tests/` | 覆盖 0 LLM、0 RAG、checkpoint、post_turn 调度 |
| `README.md` | 同步 fact_update 快速路径 |
| `docs/progress.md` | 本任务状态 |

## 行为约定

- 模板确认只表示 Agent 已接收事实，不承诺 mem0 已持久化成功。
- mem0 写入失败只记录，不撤回用户确认。
- inbound guard 阻断时不能写 mem0。

## 非范围

- 不实现 mem0 重试队列。
- 不实现 memory_profile schema。
- 不处理 chitchat。

## 测试方案

```bash
cd agent
uv run pytest tests/test_fact_update_fast_path.py tests/test_graph_invoke_mock.py tests/test_mem0_write.py -v
```

## 完成标准

- [ ] `fact_update` 无 rewrite/router/Supervisor ChatOpenAI span。
- [ ] 返回模板确认。
- [ ] 当前 turn 写入 checkpoint。
- [ ] mem0 post_turn 异步调度。
- [ ] Path Contract pass。
- [ ] README 与 `docs/progress.md` 同步。

## 进度更新

`docs/progress.md` **30** → 实现完成后改为 `✅`。
