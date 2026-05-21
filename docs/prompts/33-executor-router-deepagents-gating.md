# 33 - Executor Router 与 deepagents 分层启用

## 依赖

28, 29, 30, 31, 32

## 背景

deepagents 要保留，但不能作为所有输入的默认入口。需要根据 turn type 和任务复杂度选择执行器。

## 目标

- 引入 executor router。
- 简单输入不触发 deepagents middleware 链。
- 复杂任务仍可进入 deepagents，并在 trace 中记录触发原因。

## 范围

| 模块 | 变更 |
|------|------|
| `agent/src/graph/executors.py` 或等价模块 | 定义 executor 类型和选择逻辑 |
| `agent/src/graph/nodes.py` | Supervisor 前选择 executor |
| `agent/src/graph/supervisor.py` | 保留 deepagents，增加普通 ChatOpenAI/RAG answer 路径 |
| `agent/src/observability/tracing.py` | 记录 `executor`、`executor_reason` |
| `agent/tests/` | 覆盖简单路径不进 deepagents、复杂路径进 deepagents |
| `README.md` | 同步执行器分层 |
| `docs/progress.md` | 本任务状态 |

## Executor

| executor | 适用场景 |
|----------|----------|
| `template_executor` | fact_update、固定确认 |
| `small_chat_executor` | chitchat、轻量回复 |
| `rag_answer_executor` | RAG chunks 足够的知识问答 |
| `action_executor` | 简单 client_actions |
| `deepagents_executor` | 多步规划、复杂工具、长文档、跨页面工作流 |

## 非范围

- 不实现真流式。
- 不接服务端工具。
- 不改 client_actions 合同。

## 测试方案

```bash
cd agent
uv run pytest tests/test_executor_router.py tests/test_graph_invoke_mock.py tests/test_client_actions.py -v
```

## 完成标准

- [ ] trace 能看到 executor 和 reason。
- [ ] fact/chitchat 不进 deepagents。
- [ ] 复杂任务可进 deepagents。
- [ ] RAG 问答可走轻量 answer executor。
- [ ] README 与 `docs/progress.md` 同步。

## 进度更新

`docs/progress.md` **33** → 实现完成后改为 `✅`。

