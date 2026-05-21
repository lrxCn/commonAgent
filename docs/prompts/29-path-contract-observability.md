# 29 - Path Contract 路径契约与可观测性

## 建议执行模型

- 模型：GPT-5.5
- Reasoning：medium
- 原因：跨节点补观测字段和断言，不应大改业务路径，但需要看懂图执行流。

## 依赖

28

## 背景

不能只验收最终回答，还要验收路径是否合理。示例：`rag_skipped=true` 是对的，但如果中间多调了 rewrite/router LLM，路径仍然失败。

本任务来自 [Agent 运行时优化](../prd/agent-runtime-optimization.md) 的 Path Contract 章节。

## 目标

- 建立 Path Contract 数据结构和 metadata。
- 记录每轮“应该调用 / 实际调用”的路径信息。
- 给后续任务提供可测试的 path metrics。

## 范围

| 模块 | 变更 |
|------|------|
| `agent/src/observability/path_contract.py` 或等价模块 | 定义 path metrics、pass/fail 判断 |
| `agent/src/graph/state.py` | 增加 ephemeral `path_metrics` |
| `agent/src/graph/nodes.py` | 各节点记录 `*.called` |
| `agent/src/observability/tracing.py` | metadata 输出 `path_contract`、`path_contract_reason`、`llm_call_count` |
| `agent/tests/` | 覆盖 fact/chitchat/knowledge 基础路径契约 |
| `README.md` | 同步路径契约说明 |
| `docs/progress.md` | 本任务状态 |

## 建议字段

```text
turn_type
fast_path
rewrite.should_call / rewrite.called
rag_router.should_call / rag_router.called
rag.should_call / rag.called
supervisor.should_call / supervisor.called
llm_call_count
fallback_count
path_contract
path_contract_reason
```

## 非范围

- 不要求所有路径都立刻 pass。
- 不做 LangSmith Dataset。
- 不改业务行为。

## 测试方案

```bash
cd agent
uv run pytest tests/test_path_contract.py tests/test_tracing.py -v
```

## 完成标准

- [ ] trace metadata 能看到 path metrics。
- [ ] 至少覆盖 `fact_update`、`chitchat`、`knowledge_query` 三类契约。
- [ ] 若实际路径多调用 LLM，能标记 `path_contract=fail`。
- [ ] README 与 `docs/progress.md` 同步。

## 进度更新

`docs/progress.md` **29** → 实现完成后改为 `✅`。
