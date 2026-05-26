# 79 - memory_query 润色 Phase 3：可观测、eval 与 trace 验证

## 建议执行模型

- 模型：GPT-5.5
- Reasoning：medium
- 原因：本任务主要补可观测与评测闭环，需要核对 trace metadata、path contract 和 eval seed，不应扩大功能面。

## 新窗口执行规则

1. 先读根目录 `AGENTS.md`、`README.md`、`docs/progress.md` 和本任务卡。
2. 阅读 PRD：[agent-memory-query-polish.md](../prd/agent-memory-query-polish.md)。
3. 核对任务 76、77、78 已完成；未完成则停止。
4. 对比当前模型和 reasoning 与本节建议；如果不一致或未知，先告诉用户建议配置并等待确认，除非用户明确要求继续。
5. 只实现本任务范围，不做文档最终收口。
6. 按本任务测试计划验证。
7. 测试通过后更新 `docs/progress.md`；不要自动 push，除非用户明确要求。

## 依赖

76、77、78

## 背景

memory query 润色引入了可选小模型。需要在 trace、path metrics 和 eval 中区分 deterministic evidence、polish 调用、fallback 和最终回复，方便后续线上排障。

## 目标

- 补充 `memory_query.polish.*` metadata。
- 扩展 path metrics 或事件映射，单独记录 polish 调用。
- 新增或扩展 eval runner，校验小模型不篡改证据。
- 使用真实 trace 或 dry-run 验证 metadata 可见。

## 范围

| 模块 | 变更 |
|------|------|
| `agent/src/contracts/events.py` | 如需要，新增 polish 事件类型 |
| `agent/src/infrastructure/langsmith/metadata_mapper.py` | 映射 polish metadata |
| `agent/src/observability/path_contract.py` | 如需要，新增 memory_query_polish 字段 |
| `agent/scripts/` | 新增或扩展 memory query polish eval runner |
| `agent/evals/memory_query_polish_seed.json` | 使用 76 seed 做可执行评测 |
| `agent/tests/test_tracing.py` | 覆盖 metadata 映射 |
| `agent/tests/test_memory_query_polish.py` | 覆盖 eval/trace payload |
| `docs/progress.md` | 本任务完成后更新状态 |

## Metadata 建议

```text
memory_query.evidence_count
memory_query.evidence_fields
memory_query.missing_reason
memory_query.polish.enabled
memory_query.polish.called
memory_query.polish.model
memory_query.polish.changed
memory_query.polish.fallback_reason
memory_query.polish.validation_failed
```

## Eval 要求

必须覆盖：

- 姓名：保留姓名原文。
- 公司地址：保留地址原文。
- 偏好：不删改偏好事实。
- 缺失记忆：不得编造。
- 模型输出篡改证据：eval 失败或 fallback 成功。

## 验证方案

```bash
cd agent
uv run pytest tests/test_tracing.py tests/test_memory_query_polish.py tests/test_path_contract.py -v
uv run python scripts/run_memory_query_polish_eval.py --seed evals/memory_query_polish_seed.json --json
uv run ruff check src tests scripts
```

如真实 LangSmith 网络不可用，runner 必须支持本地 JSON 输出；真实 trace 验证可作为人工补充。

## 非范围

- 不新增生产监控看板。
- 不同步 LangSmith Dataset 为强制要求。
- 不更新 README/maps 当前契约。

## 完成标准

- [ ] trace metadata 能区分 evidence、polish、fallback。
- [ ] eval runner 覆盖 seed 并能本地运行。
- [ ] 小模型篡改事实能被测试捕获。
- [ ] `docs/progress.md` 更新 79 状态。

## 进度更新

`docs/progress.md` **79** → 实现完成后改为 `✅`；当前建议下一步改为 80。
