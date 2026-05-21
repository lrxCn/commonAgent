# 42 - 大重构 Phase 1：契约层与类型化运行对象

## 建议执行模型

- 模型：GPT-5.5
- Reasoning：high
- 原因：会引入跨模块稳定类型，需要兼容现有 graph/gateway/rag/memory 行为，同时避免一次性迁移过大。

## 依赖

41

## 背景

大重构 PRD：[Agent 大重构](../prd/agent-major-refactor.md) 的核心原则是“契约优先”。当前 `turn_type`、`executor`、`path_metrics`、SSE event、context budget、RAG result 等跨模块数据大量使用 string / dict，类型系统不能帮助维护。

本任务只新增契约层和 adapter，不强制迁移所有调用点。

## 目标

- 新增 `agent/src/contracts/`，集中定义跨模块运行契约。
- 用 Enum / dataclass / Pydantic model 表达核心值域和结构。
- 保持现有外部 API 和图行为不变。
- 给后续 ContextBundle、node 拆分、RAG 模块化、LLM Gateway 提供类型基础。

## 范围

| 模块 | 变更 |
|------|------|
| `agent/src/contracts/` | 新增契约包 |
| `agent/src/contracts/routing.py` | `TurnType`、turn reason code 常量或类型 |
| `agent/src/contracts/execution.py` | `ExecutorType`、`ExecutorDecision` |
| `agent/src/contracts/path.py` | `PathComponent`、`PathMetrics`、path metadata helper |
| `agent/src/contracts/context.py` | `ContextBudget` 占位类型，后续任务扩展 `ContextBundle` |
| `agent/src/contracts/rag.py` | `RagChunk` / `RagResult` 契约；兼容现有 `rag.retriever.RagChunk` |
| `agent/src/contracts/sse.py` | SSE event typed models |
| `agent/src/contracts/events.py` | observability event 基础类型，占位即可 |
| `agent/pyproject.toml` | 如新增顶层包，更新 `tool.uv.build-backend.module-name` |
| `agent/tests/` | 新增 contracts 单测 |
| `README.md` | 同步“契约层已存在”的当前结构说明 |
| `docs/progress.md` | 本任务状态 |

## 技术取舍

建议：

- 边界 API / JSON 事件使用 Pydantic。
- 内部纯逻辑对象优先使用 `dataclass(frozen=True)` + `Enum`。
- 不在本任务里替换全部现有 dict，先提供 adapter 和兼容函数。

## 非范围

- 不拆 `graph/nodes.py`。
- 不改 LangGraph state schema 的字段名。
- 不改变 `gateway.schemas` 的外部请求/响应模型。
- 不把 pipeline spec 接入 graph build。
- 不引入新的环境变量。

## 测试方案

```bash
cd agent
uv run pytest tests/test_settings.py tests/test_schemas.py tests/test_path_contract.py -v
uv run pytest tests -v
uv run ruff check src tests
```

## 完成标准

- [ ] `contracts/` 可被测试和业务模块导入。
- [ ] 核心枚举和 typed models 有测试覆盖。
- [ ] 现有 graph/gateway 行为不变。
- [ ] `agent/pyproject.toml` 包声明与新增顶层包一致。
- [ ] README 与 `docs/progress.md` 同步。

## 进度更新

`docs/progress.md` **42** → 实现完成后改为 `✅`。
