# 76 - memory_query 润色 Phase 0：行为冻结与评测种子

## 建议执行模型

- 模型：GPT-5.5
- Reasoning：medium
- 原因：本任务不改运行行为，但要冻结 memory_query 现状和未来润色验收样例，需准确理解 `MemoryQueryResult`、graph 路径和 path contract。

## 新窗口执行规则

1. 先读根目录 `AGENTS.md`、`README.md`、`docs/progress.md` 和本任务卡。
2. 阅读 PRD：[agent-memory-query-polish.md](../prd/agent-memory-query-polish.md)。
3. 核对 `docs/progress.md` 中本任务依赖是否完成；未完成则停止。
4. 对比当前模型和 reasoning 与本节建议；如果不一致或未知，先告诉用户建议配置并等待确认，除非用户明确要求继续。
5. 只实现本任务范围，不顺手做 77-80。
6. 按本任务测试计划验证。
7. 测试通过后更新 `docs/progress.md`；不要自动 push，除非用户明确要求。

## 依赖

75

## 背景

当前 `memory_query` 已能稳定绕开 rewrite/RAG/deepagents，直接由 `memory_query_reply` 生成确定性回答。后续要加小模型润色，必须先冻结现状，确保小模型只改变话术，不改变事实来源、路由、post_turn 行为或 fallback 语义。

## 目标

- 冻结 `MemoryQueryResult` 的当前语义。
- 冻结 `memory_query` 当前 graph 路径：`load_memory -> memory_query_reply -> post_turn_jobs`。
- 新增 memory query polish eval seed，描述未来期望话术和禁止行为。
- 不改变运行代码用户可见行为。

## 范围

| 模块 | 变更 |
|------|------|
| `agent/tests/test_memory_query_executor.py` | 补充当前 deterministic reply / evidence / missing_reason characterization |
| `agent/tests/test_path_contract.py` | 补充 memory_query 不走 rewrite/RAG/Supervisor/deepagents 的路径断言 |
| `agent/evals/` | 新增 `memory_query_polish_seed.json` 或等价 seed |
| `docs/progress.md` | 本任务完成后更新状态 |

## 实施步骤

1. 阅读 `agent/src/memory/query.py`、`agent/src/graph/nodes/executor_nodes.py`、`agent/src/graph/build.py`。
2. 为姓名、公司地址、偏好、缺失记忆、thread fallback 增加 characterization。
3. 为未来润色 seed 添加字段：`input`、`deterministic_reply`、`evidence`、`expected_polish_constraints`、`forbidden_outputs`。
4. 确保所有新增测试只断言当前行为，不引入小模型调用。

## 验证方案

```bash
cd agent
uv run pytest tests/test_memory_query_executor.py tests/test_path_contract.py -v
uv run pytest tests/test_graph_invoke_mock.py -k memory_query -v
uv run ruff check src tests
```

## 非范围

- 不新增 `memory_query_polish` 节点。
- 不新增环境变量。
- 不调用 LLM。
- 不更新 README 当前运行契约。

## 完成标准

- [ ] 当前 deterministic `MemoryQueryResult` 行为被测试冻结。
- [ ] eval seed 覆盖未来润色正反样例。
- [ ] `memory_query` 仍不触发记忆写入。
- [ ] 测试通过后 `docs/progress.md` 更新 76 状态。

## 进度更新

`docs/progress.md` **76** → 实现完成后改为 `✅`；当前建议下一步改为 77。
