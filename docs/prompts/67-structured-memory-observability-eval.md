# 67 - 结构化记忆写入 Phase 4：话术、可观测与 eval runner

## 建议执行模型

- 模型：GPT-5.4
- Reasoning：medium
- 原因：以模板/trace/eval 为主，graph 核心已在任务 66 完成；需对齐 path contract 与 seed 断言。

## 新窗口执行规则

1. 先读 `AGENTS.md`、`README.md`、`docs/progress.md`、PRD 和本任务卡。
2. 核对任务 66 是否完成。
3. 只实现本任务范围；测试通过后更新 progress 并 commit。

## 依赖

66

## 背景

structured 写入已接入 graph。本任务对齐 **用户可见话术**、**观测事件** 与 **本地 eval**，并锁定 `stored_empty` 回归。

## 目标

- 更新 `fact_update_confirm`：slot fill 成功时 Commit 话术含字段摘要（如「已记住：姓名=张三」）；fill 失败时不使用原 Commit 模板。
- 扩展 observability：`memory_write.mode`、`memory_write.record.attribute`、path contract mem0 模式字段。
- 新增 `agent/scripts/run_memory_write_eval.py`（或等价 runner）读取 `memory_write_seed.json`。
- CI 友好：默认 mock mem0；断言 fact_update 正例不得 `stored_empty`。

## 范围

| 模块 | 变更 |
|------|------|
| `agent/src/graph/nodes/executor_nodes.py` | 确认模板与 record 联动 |
| `agent/src/observability/path_contract.py` | structured/inferred mem0 模式 |
| `agent/src/observability/tracing.py` | 如有需要，事件字段 |
| `agent/scripts/run_memory_write_eval.py` | 本地 eval runner |
| `agent/evals/README.md` | runner 用法 |
| `agent/tests/test_fact_update_fast_path.py` | 话术断言 |
| `agent/tests/test_path_contract.py` | mem0 模式 |
| `docs/progress.md` | 本任务状态 |

## 话术约定

| 条件 | 话术 |
|------|------|
| record 存在 | `已记住：{label}={value}。后续我会据此为你提供个性化回答。` |
| record 缺失（不应进快路径） | 不得输出旧版纯 Commit「已收到，我会把这个信息…」 |

label 映射：name→姓名，birthday→出生年份，city→城市，job→职业，company.address→公司地址，preference→偏好。

## 非范围

- 不更新 README / docs/maps（任务 68）。
- 不做 Front 记忆 UI pending 状态。
- 不实现 Outbox/retry。

## 验证方案

```bash
cd agent
uv run pytest tests/test_fact_update_fast_path.py tests/test_path_contract.py tests/test_memory_write_eval_seed.py -v
uv run python scripts/run_memory_write_eval.py --dry-run
```

## 完成标准

- [ ] fact_update 快路径确认话术与 record 一致。
- [ ] trace/path contract 可区分 structured vs inferred。
- [ ] memory_write eval runner 对 seed 正例 pass。
- [ ] `stored_empty` regression case 在 mock 下 fail（证明回归被捕获）。

## 进度更新

`docs/progress.md` **67** → 实现完成后改为 `✅`。
