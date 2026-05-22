# 56 - 控制面 Phase 7：Intent Feedback 与控制面评测闭环

## 建议执行模型

- 模型：GPT-5.5
- Reasoning：medium
- 原因：本任务主要建设反馈和评测闭环，风险集中在数据结构、脚本入口和 LangSmith 同步兼容性。

## 依赖

55

## 背景

控制面 PRD 要求每次 fallback、误判、用户纠错都能成为可回归样本。否则 intent 改动仍会靠感觉推进，下一次又会出现局部补丁。

当前已有 `agent/evals/seed.json`、RAG eval 脚本和 LangSmith Dataset 同步脚本。本任务在此基础上新增控制面专用 seed、反馈事件和同步/校验入口。

## 目标

- 新增 `IntentFeedback` 记录 helper。
- 将用户纠错、人工 trace review、path contract 失败、fallback conflict 转换成结构化反馈样本。
- 新增或扩展脚本，把 feedback 样本合并进 intent eval seed 或同步到 LangSmith Dataset。
- 提供本地 intent/path 控制面 eval 入口。
- 规定后续控制面改动前必须跑的测试/评测。

## 范围

| 模块 | 变更 |
|------|------|
| `agent/src/intent/feedback.py` | `IntentFeedback` helper、failure_type 标准化 |
| `agent/evals/intent_seed.json` | 纳入 feedback 生成样本的目标格式 |
| `agent/evals/README.md` | 新增 feedback 和控制面 eval 说明 |
| `agent/scripts/run_intent_eval.py` | 本地 intent eval runner |
| `agent/scripts/sync_langsmith_dataset.py` | 如需要，支持 intent seed 或多 seed 输入 |
| `agent/tests/test_intent_feedback.py` | 覆盖 feedback 结构和 failure type |
| `agent/tests/test_intent_eval_runner.py` | 覆盖本地 eval runner dry path |
| `agent/tests/test_intent_eval_seed.py` | 强化 seed 结构校验 |
| `docs/progress.md` | 本任务状态 |

## feedback 样例

```python
IntentFeedback(
    original_text="我是谁",
    predicted_route="fact_update",
    corrected_route="memory_query",
    failure_type="false_positive_fact_update",
    trace_id="...",
    thread_id="...",
    user_id="...",
    note="用户是在问记忆，不是在写事实",
)
```

## failure_type 最小集合

```text
false_positive_fact_update
false_negative_fact_update
false_positive_memory_query
false_negative_memory_query
wrong_knowledge_query
wrong_client_action
low_confidence_misrouted
fallback_missing
tool_permission_misrouted
rag_empty_hallucination
```

## 本地控制面 eval 应验证

```text
intent.route
intent.speech_act
intent.domain
intent.operation
intent.confidence_min
policy.fast_path_allowed
executor.selected
fallback.allowed
```

## 非范围

- 不实现完整后台标注系统。
- 不实现前端用户反馈 UI。
- 不要求真实 LangSmith 网络同步通过；必须支持 dry-run。
- 不改变现有 RAG eval 的行为。
- 不更新 README 当前运行契约；最终文档收口在任务 57。

## 测试方案

```bash
cd agent
uv run pytest tests/test_intent_feedback.py tests/test_intent_eval_seed.py tests/test_intent_eval_runner.py -v
uv run python scripts/run_intent_eval.py --seed evals/intent_seed.json --json
uv run python scripts/sync_langsmith_dataset.py --dataset-name common-agent-intent-seed --seed evals/intent_seed.json --dry-run
uv run ruff check src tests
```

## 完成标准

- [ ] `IntentFeedback` 有稳定结构和 failure_type。
- [ ] 本地 intent eval runner 可运行。
- [ ] intent seed 可 dry-run 同步 LangSmith Dataset。
- [ ] 第一人称疑问反例进入必测 seed。
- [ ] 控制面改动的必跑验证命令写入 eval README。
- [ ] `docs/progress.md` 同步。

## 进度更新

`docs/progress.md` **56** → 实现完成后改为 `✅`。
