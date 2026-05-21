# 43 - 大重构 Phase 2：ContextBundle 单一上下文来源

## 建议执行模型

- 模型：GPT-5.5
- Reasoning：high
- 原因：会触碰 system prompt、model messages、budget metadata 和 supervisor 输入，必须严格保证模型实际输入与观测一致。

## 依赖

42

## 背景

当前 `context_assembly_node` 生成 `system_prompt/context_budget`，但 `supervisor_node` 又调用 `build_context()` 重建 model messages。这会让“观测到的上下文”和“实际进入模型的上下文”存在未来分叉风险。

本任务引入 `ContextBundle`，让上下文组装只发生一次。

## 目标

- 定义并落地 `ContextBundle`：`system_prompt`、`model_messages`、`budget`、`sources`。
- `context_assembly` 节点一次性产出 bundle。
- executor/supervisor 只消费 bundle，不重复组装上下文。
- LangSmith metadata 来自同一个 `ContextBudget`。

## 范围

| 模块 | 变更 |
|------|------|
| `agent/src/contracts/context.py` | 完整定义 `ContextBundle`、`ContextBudget`、`ContextSources` |
| `agent/src/memory/assembly.py` 或 `agent/src/domain/context/` | 新增 bundle builder；保留旧函数兼容层 |
| `agent/src/graph/state.py` | 增加或替换单轮 `context_bundle` 字段；必要时保留 `system_prompt/context_budget` 兼容 |
| `agent/src/graph/nodes.py` | `context_assembly_node` 产出 bundle；`supervisor_node` 消费 bundle |
| `agent/src/graph/supervisor.py` | 确保 answer/deepagents executor 接收 bundle 中的 system/messages |
| `agent/src/observability/tracing.py` | metadata 从 `ContextBudget` 读取 |
| `agent/tests/` | 覆盖 bundle 内容、预算、supervisor 输入一致性 |
| `README.md` | 同步 LangGraph/context 契约 |
| `docs/progress.md` | 本任务状态 |

## 兼容要求

- 如果保留 `system_prompt` 和 `context_budget` 字段，必须注明它们是由 `ContextBundle` 派生的兼容字段。
- 测试应能断言 `invoke_answer_executor()` / `invoke_supervisor()` 收到的 messages 与 bundle 一致。
- `current_human`、`original_human_content` metadata 的处理只在 bundle builder 中发生一次。

## 非范围

- 不拆 graph node 文件。
- 不改 RAG 检索算法。
- 不改 prompt 文案，除非为了保持原有输出必要。
- 不改变 SSE/client_actions 行为。

## 测试方案

```bash
cd agent
uv run pytest tests/test_context_assembly.py tests/test_supervisor.py tests/test_graph_invoke_mock.py tests/test_tracing.py -v
uv run pytest tests -v
uv run ruff check src tests
```

## 完成标准

- [ ] `ContextBundle` 成为模型上下文单一来源。
- [ ] `context_assembly_node` 和 `supervisor_node` 不再各自独立组装上下文。
- [ ] context budget metadata 与实际模型输入一致。
- [ ] 旧测试和新增一致性测试通过。
- [ ] README 与 `docs/progress.md` 同步。

## 进度更新

`docs/progress.md` **43** → 实现完成后改为 `✅`。
