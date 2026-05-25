# 66 - 结构化记忆写入 Phase 3：Graph 接入与 post_turn 双轨路由

## 建议执行模型

- 模型：GPT-5.4
- Reasoning：high
- 原因：修改 graph state、load_memory/post_turn 节点与 fact_update 路径，需保证 fast path、Policy denied、memory_query 跳过等行为不回归。

## 新窗口执行规则

1. 先读 `AGENTS.md`、`README.md`、`docs/progress.md`、PRD 和本任务卡。
2. 核对任务 65 是否完成。
3. 只实现本任务范围；测试通过后更新 progress 并 commit。

## 依赖

65

## 背景

structured record 与 store 函数已就绪。本任务将 **Policy 通过的 fact_update** 接入主图：在分类阶段生成 record，post_turn 按 record 走 structured store，其他路径仍 infer。

## 目标

- `AgentState` 增加 ephemeral 字段 `memory_write_record`（`StructuredMemoryRecord | None`）。
- `load_memory_node`（或紧邻节点）：Policy 通过 fact_update 时调用 slot fill，写入 state。
- `post_turn_jobs` / `post_turn.py`：有 record 则 `store_structured_record`，否则 `extract_and_store`。
- 同一 turn structured 与 infer **互斥**。
- 保持：`policy_denied fact_update`、`memory_query`、`inbound_blocked` 不调度 mem0 写入。

## 范围

| 模块 | 变更 |
|------|------|
| `agent/src/graph/state.py` | ephemeral `memory_write_record` |
| `agent/src/graph/nodes/memory_nodes.py` | slot fill 写入 state |
| `agent/src/graph/nodes/post_turn_nodes.py` | 传递 record 到 scheduler |
| `agent/src/memory/post_turn.py` | 双轨路由 |
| `agent/tests/test_fact_update_fast_path.py` | structured 写入断言 |
| `agent/tests/test_post_turn_graph.py` | skip 路径无回归 |
| `agent/tests/test_graph_invoke_mock.py` | 如有必要更新 |
| `docs/progress.md` | 本任务状态 |

## 行为约定

- slot fill 返回 `None` 但 Policy 通过：不进入 fact_update_confirm 快路径 Commit（降级 conservative 路径或 infer-only post_turn，须 trace `structured_fill_failed`）——与 PRD 一致。
- `source_turn_id` 使用 `thread_id` + 可复现 turn 标识。
- post_turn 仍 fire-and-forget，不阻塞 invoke。

## 非范围

- 不改用户确认模板文案（任务 67）。
- 不更新 README/maps（任务 68）。
- 不新增 eval runner（任务 67）。

## 验证方案

```bash
cd agent
uv run pytest tests/test_fact_update_fast_path.py tests/test_post_turn_graph.py tests/test_mem0_write.py tests/test_policy_gate.py -v
```

## 完成标准

- [ ] Policy 通过 fact_update 调度 structured store（mock 断言 infer=False）。
- [ ] memory_query / policy denied 仍 skip mem0 write。
- [ ] general_chat 仍走 infer post_turn（如有调度）。
- [ ] Path contract 对 fact_update 记录 structured mem0 模式。

## 进度更新

`docs/progress.md` **66** → 实现完成后改为 `✅`。
