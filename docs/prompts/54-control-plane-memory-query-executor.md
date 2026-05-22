# 54 - 控制面 Phase 5：memory_query 一等路径与记忆回答执行器

## 建议执行模型

- 模型：GPT-5.5
- Reasoning：high
- 原因：本任务新增用户记忆读取路径，会改变「我是谁」等问题的实际回复，需要严格区分记忆查询、记忆写入和普通聊天，并防止模型猜测用户身份。

## 依赖

53

## 背景

控制面 PRD 明确「我是谁」「我叫什么」「我公司在哪」不是事实写入，而是用户对长期记忆/画像的查询。当前系统没有 `memory_query` 一等路径，只能落到 `general_chat`、Supervisor 或被误判为 `fact_update`。

本任务新增 memory executor，使记忆查询基于 `memory_profile`、mem0 memories 和当前 thread 可靠上下文回答。查不到时必须明说，不得编造。

## 目标

- `memory_query` 成为 graph 一等路由。
- 新增 memory query executor。
- 回答只基于可信记忆来源，不允许模型凭空猜测。
- 记忆缺失时返回诚实缺失回复，并可邀请用户补充。
- `memory_query` 不触发 mem0 写入。

## 范围

| 模块 | 变更 |
|------|------|
| `agent/src/contracts/routing.py` | 如旧 `TurnType` 仍需扩展，加入 `MEMORY_QUERY` 兼容值 |
| `agent/src/contracts/execution.py` | 新增 `memory_executor` 或等价 executor type |
| `agent/src/memory/query.py` | 新增 memory query 解析、证据选择和回答构造 |
| `agent/src/graph/executors.py` | executor router 支持 `memory_query` |
| `agent/src/graph/nodes/routing_nodes.py` | `memory_query` 路由到 memory executor |
| `agent/src/graph/nodes/executor_nodes.py` | 新增 `memory_query_reply_node` 或等价节点 |
| `agent/src/memory/assembly.py` | 如需要，暴露 memory_profile / mem0 证据选择 helper |
| `agent/src/observability/` | 记录 memory_query evidence 和 missing reason |
| `agent/tests/test_memory_query_executor.py` | 覆盖有记忆、无记忆、冲突记忆、公司记忆 |
| `agent/tests/test_path_contract.py` | 覆盖 `memory_query` 路径契约 |
| `agent/tests/test_graph_invoke_mock.py` | 覆盖端到端 mock invoke |
| `docs/progress.md` | 本任务状态 |

## 回答来源优先级

建议顺序：

1. `memory_profile` 结构化字段。
2. mem0 memories 中未归类但相关的自由文本。
3. 当前 thread 中明确、可靠、最近的用户自述。

不允许使用：

- RAG 企业知识库回答用户私人身份。
- 模型常识推测用户是谁。
- 不相关历史消息。

## 必测输入

| 输入 | 期望 |
|------|------|
| 我是谁 | 有 name/profile 时回答；没有时说没有可靠记录 |
| 我叫什么 | 只回答记忆中的姓名 |
| 我的生日是什么 | 只回答记忆中的生日/年份 |
| 我公司在哪 | 只回答记忆中的公司地址 |
| 我喜欢什么 | 基于偏好记忆回答 |

## 缺失回复约定

当没有可靠记忆时，返回类似：

```text
我目前没有可靠记录你是谁。你可以告诉我你的名字或身份，我之后会按你的授权记住。
```

语义要求：

- 不说“我忘了”，因为可能从未记录。
- 不猜测。
- 不触发 `fact_update`。
- 不调度 mem0 写入。

## 非范围

- 不实现复杂记忆冲突解决 UI。
- 不实现用户主动删除记忆。
- 不改变 mem0 写入策略。
- 不改变 RAG 检索。
- 不新增服务端工具。
- 不更新 README 当前运行契约；最终文档收口在任务 57。

## 测试方案

```bash
cd agent
uv run pytest tests/test_memory_query_executor.py tests/test_policy_gate.py tests/test_fact_update_fast_path.py -v
uv run pytest tests/test_graph_invoke_mock.py tests/test_path_contract.py tests/test_context_assembly.py -v
uv run ruff check src tests
```

## 完成标准

- [ ] `memory_query` 有一等 executor 和 graph 路由。
- [ ] 「我是谁」类问题不进入 RAG、fact_update 或 deepagents。
- [ ] 查不到记忆时诚实回复。
- [ ] `memory_query` 不调度 mem0 写入。
- [ ] path contract 覆盖 `memory_query`。
- [ ] `docs/progress.md` 同步。

## 进度更新

`docs/progress.md` **54** → 实现完成后改为 `✅`。
