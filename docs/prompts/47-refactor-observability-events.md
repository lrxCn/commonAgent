# 47 - 大重构 Phase 6：Observability 事件化与 LangSmith 适配

## 建议执行模型

- 模型：GPT-5.5
- Reasoning：high
- 原因：会调整 trace metadata 的生产方式，必须保持现有 LangSmith 关键字段兼容，同时让业务测试可断言事件。

## 依赖

46

## 背景

当前业务模块中分散调用 `attach_run_metadata()`，观测字段和业务逻辑耦合较紧。后续如果继续拆分 domain/application/infrastructure，直接写 LangSmith metadata 会让纯逻辑模块难以测试，也容易在重构中漏字段。

本任务引入 domain events，由 LangSmith adapter 将事件转换为 metadata/span。

## 目标

- 定义 observability events。
- 提供 per-turn event collector 或同步 event bus。
- LangSmith adapter 订阅事件并输出兼容 metadata。
- 逐步减少业务代码直接调用 `attach_run_metadata()`。
- 保留现有 trace key，避免看板和测试断裂。

## 范围

| 模块 | 变更 |
|------|------|
| `agent/src/contracts/events.py` | 定义事件类型和 payload |
| `agent/src/infrastructure/langsmith/` | LangSmith adapter / metadata mapper |
| `agent/src/observability/tracing.py` | 保留兼容 facade，接入事件 mapper |
| `agent/src/observability/path_contract.py` | 可保留现状或输出 PathMetrics event |
| `agent/src/graph/`、`domain/`、`rag/`、`memory/` | 逐步将关键 metadata 改为 emit event |
| `agent/tests/` | 事件测试、metadata 兼容测试、trace helper 测试 |
| `README.md` | 同步 observability 边界 |
| `docs/progress.md` | 本任务状态 |

## 事件建议

| Event | 触发点 |
|-------|--------|
| `TurnClassified` | turn_type 决策完成 |
| `RewriteCompleted` / `RewriteSkipped` | rewrite 阶段 |
| `RagRouted` | RAG router 阶段 |
| `RagRetrieved` | 检索完成 |
| `ExecutorChosen` | executor router 阶段 |
| `ContextBudgetComputed` | ContextBundle 生成 |
| `ClientActionsParsed` | client_actions 解析 |
| `GuardrailChecked` | inbound/outbound/streaming guard |
| `PostTurnScheduled` | summary/mem0 写入调度 |
| `LlmCallCompleted` | LLM Gateway 调用完成 |

## 兼容要求

- 现有测试依赖的 metadata key 保持。
- `attach_run_metadata()` 可继续作为兼容 API 存在，但新代码优先 emit event。
- LangSmith 不可用时事件系统应 no-op，不影响业务路径。
- 测试环境仍默认禁用 LangSmith export。

## 非范围

- 不接入外部 metrics 系统。
- 不改 LangSmith 项目配置。
- 不改变业务路径和模型调用。
- 不移除所有旧 trace helper，除非有明确兼容替代。

## 测试方案

```bash
cd agent
uv run pytest tests/test_tracing.py tests/test_path_contract.py tests/test_graph_invoke_mock.py tests/test_chat_sse.py -v
uv run pytest tests -v
uv run ruff check src tests
```

## 完成标准

- [ ] 核心事件类型存在并有测试。
- [ ] LangSmith adapter 能把事件转换为原有关键 metadata。
- [ ] 业务层关键路径可通过事件测试断言。
- [ ] LangSmith export disabled 时不影响测试和业务。
- [ ] README 与 `docs/progress.md` 同步。

## 进度更新

`docs/progress.md` **47** → 实现完成后改为 `✅`。
