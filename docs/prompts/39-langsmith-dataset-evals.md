# 39 - LangSmith Dataset 评测集与本地 seed

## 依赖

21, 29

## 背景

RAG 和 Agent 路径不能只靠手感。PRD 决策：LangSmith Dataset 为主，本地 JSON/Markdown seed 为辅。

## 目标

- 建立本地最小评测 seed。
- 提供同步/运行 LangSmith Dataset 的脚本或说明。
- 同时评估 answer correctness 与 path correctness。

## 范围

| 模块 | 变更 |
|------|------|
| `agent/evals/` | 新增 seed 数据和运行脚本 |
| `agent/scripts/` | 如需要，新增 LangSmith Dataset 同步脚本 |
| `agent/tests/` | smoke test seed 格式 |
| `README.md` | 同步评测运行方式 |
| `docs/progress.md` | 本任务状态 |

## Seed 字段建议

```json
{
  "id": "fact-city-001",
  "input": "我生活在哈尔滨",
  "context": {"user_id": "u1", "role_id": "role-sales", "tools": []},
  "expected_answer": {"kind": "template_confirm"},
  "expected_path": {
    "turn_type": "fact_update",
    "llm_call_count_max": 0,
    "rag_called": false
  }
}
```

## 非范围

- 不要求接入 CI。
- 不实现复杂自动评分器。
- 不改 RAG 算法。

## 测试方案

```bash
cd agent
uv run pytest tests/test_evals_seed.py -v
```

## 完成标准

- [ ] 本地 seed 至少覆盖 fact/chitchat/knowledge/ambiguous/client_action。
- [ ] 文档说明如何同步或创建 LangSmith Dataset。
- [ ] path_score 与 answer_score 分开。
- [ ] README 与 `docs/progress.md` 同步。

## 进度更新

`docs/progress.md` **39** → 实现完成后改为 `✅`。

