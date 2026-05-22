# 55 - 控制面 Phase 6：Agent 级 Fallback Manager 与降级策略

## 建议执行模型

- 模型：GPT-5.5
- Reasoning：high
- 原因：本任务把分散在各节点的失败处理收敛成显式 fallback 策略，涉及 intent、memory、RAG、tool、schema、LLM、guardrail 等多层失败语义。

## 依赖

54

## 背景

控制面 PRD 明确：Agent 级兜底不是“最后交给大模型试试看”，而是系统级降级与恢复机制。

当前系统已经有部分分散 fallback，例如 RAG dense 失败后 BM25 fallback、rerank HTTP 失败后稳定顺序分数、流式出站护栏撤回等。但这些失败没有统一的控制面语义，也缺少统一 trace 字段和策略矩阵。

## 目标

- 新增 Fallback Manager，统一表达失败层、失败原因、降级动作和用户可见策略。
- 明确 intent low confidence、intent conflict、memory missing、RAG empty、tool unavailable、LLM timeout、schema invalid、output guard failed 等场景的处理。
- 将 fallback 结果写入 path metrics / observability metadata。
- 不用 deepagents 作为默认兜底。

## 范围

| 模块 | 变更 |
|------|------|
| `agent/src/contracts/fallback.py` 或 `contracts/intent.py` | `FallbackLayer`、`FallbackAction`、`FallbackDecision` |
| `agent/src/intent/fallback.py` | intent / policy 层 fallback 决策 |
| `agent/src/domain/rag/` | 暴露 RAG empty / weak hit fallback reason |
| `agent/src/graph/nodes/` | 在关键节点消费或记录 fallback decision |
| `agent/src/contracts/events.py` | 新增 `FallbackTriggered` 事件 |
| `agent/src/infrastructure/langsmith/metadata_mapper.py` | 映射 fallback metadata |
| `agent/src/observability/path_contract.py` | 如需要，记录 fallback allowed / triggered |
| `agent/tests/test_fallback_manager.py` | 覆盖策略矩阵 |
| `agent/tests/test_path_contract.py` | 覆盖 fallback 观测 |
| `agent/tests/test_rag_retrieval.py` / `test_memory_query_executor.py` | 覆盖 RAG empty / memory missing |
| `docs/progress.md` | 本任务状态 |

## 策略矩阵

| 失败层 | 条件 | 兜底策略 |
|--------|------|----------|
| intent | 低置信 | 问澄清问题，或走保守 executor |
| intent | 规则与模型冲突 | 禁止 fast path，记录 conflict，必要时澄清 |
| memory | 查不到用户记忆 | 明说没有可靠记录，邀请用户补充 |
| memory | 写入后台失败 | 不阻塞本轮，记录失败，进入补偿或告警 |
| RAG | 检索为空 | 明说知识库未找到来源，避免编造引用 |
| RAG | 召回弱 | 二查或澄清，不直接给确定性答案 |
| tool | 工具不可用或无权限 | 明说不可用，不假装执行 |
| tool | 高风险动作 | 标记需要 HITL，具体审批实现可后续任务处理 |
| LLM | timeout | 重试一次、降级模型或模板回复 |
| schema | 结构化输出非法 | repair 一次，仍失败则安全错误回复 |
| output_guard | 输出违规 | retract / replace / refusal |
| checkpoint | 状态写入失败 | 不继续执行副作用动作，返回可恢复错误 |

## 观测字段

```text
fallback.triggered
fallback.layer
fallback.reason
fallback.action
fallback.user_visible
fallback.recovered
fallback.original_route
fallback.final_route
```

## 非范围

- 不实现完整人工审批 UI。
- 不新增服务端工具执行链路。
- 不重写所有异常处理；优先覆盖主链路和控制面相关失败。
- 不改变 Front -> Back -> Agent 边界。
- 不更新 README 当前运行契约；最终文档收口在任务 57。

## 测试方案

```bash
cd agent
uv run pytest tests/test_fallback_manager.py tests/test_memory_query_executor.py tests/test_rag_retrieval.py -v
uv run pytest tests/test_path_contract.py tests/test_tracing.py tests/test_chat_sse.py -v
uv run ruff check src tests
```

如果外部服务缺失，只跑 mock/unit 覆盖，并说明 live fallback 未跑。

## 完成标准

- [ ] FallbackDecision 有稳定契约和测试。
- [ ] 主链路至少覆盖 intent、memory、RAG、tool、LLM/schema、output guard 的 fallback metadata。
- [ ] RAG empty 不伪造来源。
- [ ] tool unavailable 不承诺已执行。
- [ ] deepagents 不作为低置信全局兜底。
- [ ] `docs/progress.md` 同步。

## 进度更新

`docs/progress.md` **55** → 实现完成后改为 `✅`。
