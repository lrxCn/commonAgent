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
  - 当前 seed 只用于契约和后续 shadow/eval 入口，不改变现有 graph 运行路径。

## 运行

```bash
cd agent
uv run pytest tests/test_evals_seed.py -v
uv run pytest tests/test_intent_eval_seed.py -v
uv run python scripts/run_rag_eval.py --seed evals/seed.json --json
uv run python scripts/sync_langsmith_dataset.py --dataset-name common-agent-seed --seed evals/seed.json --dry-run
```

去掉 `--dry-run` 后会按本地 seed 创建或更新 LangSmith Dataset 样本。
