# 28 - Turn Type 路由层

## 建议执行模型

- 模型：GPT-5.5
- Reasoning：medium
- 原因：新增图内分类与 metadata，风险中等，重点是保持现有执行路径不变。

## 依赖

27

## 背景

运行时优化 PRD：[Agent 运行时优化](../prd/agent-runtime-optimization.md) 要求先判断本轮 `turn_type`，再决定 rewrite、RAG、Supervisor、deepagents 是否需要参与。

当前 rewrite/router 各自维护规则，导致规则分散、路径难验收。

## 目标

- 新增统一 `turn_type` 决策层。
- 只做分类和 metadata，不改变主图执行路径。
- 为后续 fast path、executor router、Path Contract 打基础。

## 范围

| 模块 | 变更 |
|------|------|
| `agent/src/graph/turn_type.py` 或等价模块 | 定义 `TurnType`、`classify_turn_type()`、reason code |
| `agent/src/graph/state.py` | 增加单轮 ephemeral `turn_type`、`turn_type_reason` |
| `agent/src/graph/nodes.py` | 在 `load_memory` 后写入 turn type，继续走现有路径 |
| `agent/src/observability/tracing.py` | metadata 补 `turn_type`、`turn_type_reason` |
| `agent/tests/` | 覆盖分类规则和图内 state 传递 |
| `README.md` | 同步 turn type 目标态 |
| `docs/progress.md` | 本任务状态 |

## Turn Type

第一期至少支持：

| turn_type | 示例 |
|-----------|------|
| `fact_update` | 我生活在哈尔滨 / 我公司在天翔街188号 |
| `chitchat` | 你好 / 谢谢 |
| `knowledge_query` | 报销制度是什么 |
| `client_action` | 打开 pageA |
| `ambiguous` | 它需要什么材料 / 继续说 |
| `general_chat` | 非知识库普通聊天 |

## 非范围

- 不跳过 rewrite/RAG/Supervisor。
- 不实现 fact_update 快速返回。
- 不实现 deepagents 分层执行。
- 不改 SSE。

## 测试方案

```bash
cd agent
uv run pytest tests/test_turn_type.py tests/test_graph_invoke_mock.py -v
```

## 完成标准

- [ ] `classify_turn_type()` 有明确 reason code。
- [ ] 图内能在 LangSmith metadata 看到 `turn_type`。
- [ ] 不改变现有行为，只新增分类结果。
- [ ] README 与 `docs/progress.md` 同步。

## 进度更新

`docs/progress.md` **28** → 实现完成后改为 `✅`。
