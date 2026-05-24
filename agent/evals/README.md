# Evals

本目录保存本地版本管理的评测 seed，用于 LangSmith Dataset 同步和本地 smoke test。

## 文件

- `seed.json`
  - 最小评测集，覆盖 `fact_update`、`chitchat`、`knowledge_query`、`ambiguous`、`client_action`。
  - RAG 样例可带 `kb_fixture`，并在 `expected_answer` 中声明 `expected_doc_ids` / `forbidden_doc_ids`，用于检索命中和 `role_id` 防越权评测。
  - `expected_answer` 只描述答案类别或关键约束，不做复杂自动判分。
  - `expected_path` 单独描述路径契约，和答案预期分开维护。
- `intent_seed.json`
  - 控制面 intent seed，覆盖 `fact_update`、`memory_query`、`knowledge_query`、`client_action`、`ambiguous`、`general_chat`、`chitchat`、`safety_refusal`。
  - 每行包含 `input`、`context` 和 `expected_intent`，其中 `expected_intent.route` 是未来 `turn_type` 兼容来源。
  - 可选 `feedback` 字段保存人工纠错、path contract 失败或 fallback conflict 转换出的样本来源。
  - 当前 seed 只用于契约和本地控制面 eval 入口，不改变现有 graph 运行路径。

## Feedback

`IntentFeedback` 是控制面回归样本的最小结构，来源可以是用户纠错、人工 trace review、path contract 失败或 fallback conflict。标准 `failure_type` 集合为：

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

人工确认后的 feedback 可转换成 `intent_seed.json` 行，并在 `feedback` 字段保留 `predicted_route`、`corrected_route`、`failure_type`、`trace_id`、`thread_id`、`user_id` 与备注。第一人称疑问误判为 `fact_update` 的反例必须保留在 seed 中。

## 运行

```bash
cd agent
uv run pytest tests/test_evals_seed.py -v
uv run pytest tests/test_intent_eval_seed.py -v
uv run python scripts/run_rag_eval.py --seed evals/seed.json --json
uv run python scripts/run_intent_eval.py --seed evals/intent_seed.json --json
uv run python scripts/sync_langsmith_dataset.py --dataset-name common-agent-seed --seed evals/seed.json --dry-run
uv run python scripts/sync_langsmith_dataset.py --dataset-name common-agent-intent-seed --seed evals/intent_seed.json --dry-run
```

去掉 `--dry-run` 后会按本地 seed 创建或更新 LangSmith Dataset 样本。

控制面改动前至少运行：

```bash
cd agent
uv run pytest tests/test_intent_feedback.py tests/test_intent_eval_seed.py tests/test_intent_eval_runner.py -v
uv run python scripts/run_intent_eval.py --seed evals/intent_seed.json --json
uv run python scripts/sync_langsmith_dataset.py --dataset-name common-agent-intent-seed --seed evals/intent_seed.json --dry-run
```
