# 78 - memory_query 润色 Phase 2：Graph 接入与 fallback

## 建议执行模型

- 模型：GPT-5.5
- Reasoning：high
- 原因：本任务修改主图拓扑和 memory_query 用户可见路径，必须保护 fast path、post_turn skip write、path metrics 和 fallback 行为。

## 新窗口执行规则

1. 先读根目录 `AGENTS.md`、`README.md`、`docs/progress.md` 和本任务卡。
2. 阅读 PRD：[agent-memory-query-polish.md](../prd/agent-memory-query-polish.md)。
3. 核对任务 76、77 已完成；未完成则停止。
4. 对比当前模型和 reasoning 与本节建议；如果不一致或未知，先告诉用户建议配置并等待确认，除非用户明确要求继续。
5. 只实现本任务范围，不做文档最终收口。
6. 按本任务测试计划验证。
7. 测试通过后更新 `docs/progress.md`；不要自动 push，除非用户明确要求。

## 依赖

76、77

## 背景

当前 graph 是 `load_memory -> memory_query_reply -> post_turn_jobs`。本任务新增 `memory_query_polish` 节点，使确定性回答与小模型话术分层可观测。

目标形态：

```text
load_memory -> memory_query_reply -> memory_query_polish -> post_turn_jobs
```

## 目标

- 新增 `memory_query_polish_node`。
- 主图接入 `memory_query_reply -> memory_query_polish -> post_turn_jobs`。
- `MEMORY_QUERY_POLISH_USE_LLM=false` 时保持原回复 passthrough。
- 小模型失败时回退 deterministic draft。
- `memory_query` 仍不触发 memory write。

## 范围

| 模块 | 变更 |
|------|------|
| `agent/src/graph/build.py` | 新增节点与边 |
| `agent/src/graph/nodes/executor_nodes.py` 或新节点文件 | 新增 `memory_query_polish_node` |
| `agent/src/graph/state.py` | 如需要，新增 ephemeral polish result 字段 |
| `agent/src/graph/nodes/__init__.py` | 导出新节点 |
| `agent/tests/test_graph_compile.py` | 覆盖 graph 拓扑新增节点 |
| `agent/tests/test_memory_query_executor.py` | 覆盖 graph 开关、回退和最终 message |
| `agent/tests/test_post_turn_graph.py` | 覆盖 polish 后仍 skip memory write |
| `agent/tests/test_path_contract.py` | 覆盖路径不走 rewrite/RAG/Supervisor |
| `docs/progress.md` | 本任务完成后更新状态 |

## Graph 要求

- `memory_query_reply` 仍负责调用 `answer_memory_query()`。
- `memory_query_polish` 读取 deterministic draft 和 evidence。
- `memory_query_polish` 写入最终 assistant message 或替换上一条草稿的方式必须明确测试。
- 若实现选择让 `memory_query_reply` 不立即 append message，而只写 draft，则必须同步更新测试和契约说明。

优先实现建议：

1. `memory_query_reply` 生成 draft 和 `MemoryQueryResult`。
2. `memory_query_polish` 根据开关生成 final reply。
3. 最终只 checkpoint 一条 assistant reply，避免 history 中出现 draft + polished 两条。

## 验证方案

```bash
cd agent
uv run pytest tests/test_graph_compile.py tests/test_memory_query_executor.py tests/test_post_turn_graph.py tests/test_path_contract.py -v
uv run pytest tests/test_graph_invoke_mock.py -k memory_query -v
uv run ruff check src tests
```

## 非范围

- 不做 LangSmith Dataset 同步。
- 不更新 README/maps 当前契约。
- 不调整 memory_query intent 识别规则。

## 完成标准

- [ ] 主图出现 `memory_query_polish` 节点。
- [ ] 关闭开关时用户可见行为不回归。
- [ ] 打开开关且 mock LLM 成功时最终回复为润色文本。
- [ ] 小模型失败/校验失败时回退 deterministic draft。
- [ ] post_turn 仍跳过 memory write。
- [ ] `docs/progress.md` 更新 78 状态。

## 进度更新

`docs/progress.md` **78** → 实现完成后改为 `✅`；当前建议下一步改为 79。
