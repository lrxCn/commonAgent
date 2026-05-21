# 44 - 大重构 Phase 3：Graph Nodes 拆分为薄适配器

## 建议执行模型

- 模型：GPT-5.5
- Reasoning：high
- 原因：这是结构性迁移，会移动 graph 主链路代码。要求行为不变、导入路径兼容、测试和 monkeypatch helper 同步。

## 依赖

43

## 背景

`agent/src/graph/nodes.py` 当前承载 memory、routing、RAG、context、executor、client_actions、post_turn 等多个阶段，是人和 AI 后续维护的主要认知瓶颈。

本任务只做结构拆分和 adapter 收敛，不改变业务行为。

## 目标

- 将 `graph/nodes.py` 拆成按阶段组织的小模块。
- LangGraph node 函数保持薄适配器：读取 state/context，调用 service，返回 patch。
- 保持 `from graph.nodes import ...` 兼容，减少测试和外部调用破坏。
- 为后续 domain/application 分层迁移打基础。

## 范围

| 模块 | 变更 |
|------|------|
| `agent/src/graph/nodes.py` | 迁移为 `graph/nodes/` package 或保留 facade |
| `agent/src/graph/nodes/guardrail_nodes.py` | inbound/outbound guard nodes |
| `agent/src/graph/nodes/memory_nodes.py` | load memory、history、summary 相关 nodes |
| `agent/src/graph/nodes/routing_nodes.py` | route functions、turn/executor routing adapter |
| `agent/src/graph/nodes/rag_nodes.py` | rewrite、rag_router、rag_retrieval、rag_subagent adapter |
| `agent/src/graph/nodes/context_nodes.py` | context assembly adapter |
| `agent/src/graph/nodes/executor_nodes.py` | supervisor/action/chitchat/fact_update adapter |
| `agent/src/graph/nodes/post_turn_nodes.py` | post_turn jobs adapter |
| `agent/src/graph/build.py` | 导入路径同步 |
| `agent/tests/` | monkeypatch 路径、helper、覆盖同步 |
| `README.md` | 同步目录结构 |
| `docs/progress.md` | 本任务状态 |

## 兼容策略

优先方案：

- 将 `graph/nodes.py` 替换为 `graph/nodes/__init__.py` facade。
- `__init__.py` 继续 re-export 原有 node 函数名和 route 函数名。
- 现有 `from graph.nodes import inbound_guard_node` 保持可用。

如果一次性文件改动过大，可先创建 `graph/node_adapters/`，再在后续任务迁移为 `graph/nodes/` package。但任务完成时必须保证文件边界清晰。

## 非范围

- 不改 graph 拓扑。
- 不改 state 字段名。
- 不改 RAG/LLM/mem0 业务逻辑。
- 不引入新的 pipeline runner。

## 测试方案

```bash
cd agent
uv run pytest tests/test_graph_compile.py tests/test_graph_invoke_mock.py tests/test_fact_update_fast_path.py tests/test_chitchat_executor.py tests/test_client_actions.py tests/test_post_turn_graph.py -v
uv run pytest tests -v
uv run ruff check src tests
```

## 完成标准

- [ ] 单个 graph node 模块职责清晰，主 facade 不再承载大量业务逻辑。
- [ ] `graph.build.compile_graph()` 拓扑不变。
- [ ] 原有导入路径或 facade 兼容。
- [ ] 典型路径测试全部通过。
- [ ] README 与 `docs/progress.md` 同步。

## 进度更新

`docs/progress.md` **44** → 实现完成后改为 `✅`。
