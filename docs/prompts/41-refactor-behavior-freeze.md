# 41 - 大重构 Phase 0：行为冻结与验证入口

## 建议执行模型

- 模型：GPT-5.5
- Reasoning：high
- 原因：这是大重构前的护栏任务，需要读懂现有主链路、测试入口、state 生命周期与 SSE/client_actions 合约，避免后续任务在无保护下改出行为漂移。

## 依赖

40

## 背景

大重构 PRD：[Agent 大重构](../prd/agent-major-refactor.md) 要求先冻结当前行为，再逐步迁移结构。

当前代码已具备核心能力，但存在几个重构风险点：

- `agent/Makefile` 的测试入口与当前 `agent/tests/test_*.py` 目录不一致。
- `AgentState` 的单轮字段依赖 `EphemeralValue` 与 `_EPHEMERAL_CARRY_KEYS` 手工同步。
- 典型 turn path 虽有测试，但还需要更明确的 characterization tests 锁住“当前行为”。
- SSE 事件类型已有 `token` / `done` / `client_actions` / `retract` / `replace` / `error`，需要契约测试防止后续漂移。

## 目标

- 修正本地验证入口，使 `make test` 与 README 中推荐命令可实际运行当前测试。
- 增加 state lifecycle 守护测试，发现 `AgentState` 与 carry keys 不一致。
- 增加典型 turn path characterization tests，锁住 01-40 已完成行为。
- 增加 SSE event contract tests，锁住事件形状。
- 不改变业务行为。

## 范围

| 模块 | 变更 |
|------|------|
| `agent/Makefile` | 修正 `test` / `integration-tests` 目标，匹配当前测试目录和 marker |
| `agent/tests/` | 新增或扩展 state lifecycle、pipeline path、SSE event contract 测试 |
| `agent/tests/support/` | 如需要，抽取 graph mock / path assertion helper |
| `README.md` | 同步当前推荐验证命令，只描述现状，不写入未来重构结构 |
| `docs/progress.md` | 本任务状态 |

## 建议新增测试

| 测试 | 断言 |
|------|------|
| `test_state_lifecycle.py` | `AgentState` 中所有非 `messages` 的 `EphemeralValue` 字段都被 carry 或明确标记为不需要 carry |
| `test_pipeline_characterization.py` | fact_update/chitchat/knowledge_query/client_action/ambiguous 的路径和 executor 不漂移 |
| `test_sse_event_contract.py` | SSE frame 结构、事件类型、`segment_id`、client_actions JSON 形状稳定 |
| `test_validation_entrypoints.py` | `Makefile` 指向的测试目录或 marker 存在 |

## 非范围

- 不新增 `contracts/`。
- 不拆 `graph/nodes.py`。
- 不改 RAG、LLM、mem0、LangSmith 行为。
- 不改变 Front -> Back -> Agent 边界。
- 不重写 README 的架构章节。

## 测试方案

```bash
cd agent
uv run pytest tests/test_settings.py tests/test_graph_invoke_mock.py tests/test_path_contract.py tests/test_chat_sse.py -v
uv run pytest tests -v
uv run ruff check src tests
```

如果本地 Postgres/Qdrant/外部 LLM 缺失，只运行 mock/unit 覆盖，并在结果中说明跳过的 live path。

## 完成标准

- [ ] `make test` 可运行当前单元测试集，或 README 明确推荐直接使用 `uv run pytest tests -v`。
- [ ] 新增 state lifecycle 守护测试。
- [ ] 新增或强化典型 turn path characterization tests。
- [ ] 新增 SSE event contract tests。
- [ ] 不改变现有用户可见行为。
- [ ] README 与 `docs/progress.md` 同步。

## 进度更新

`docs/progress.md` **41** → 实现完成后改为 `✅`。
