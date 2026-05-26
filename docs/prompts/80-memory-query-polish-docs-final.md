# 80 - memory_query 润色 Phase 4：README、代码地图与文档最终对齐

## 建议执行模型

- 模型：GPT-5.5
- Reasoning：medium
- 原因：本任务是文档收口，需核对代码实际状态、README 当前运行契约、docs/maps 导航和 PRD 落地偏差，避免把未来方案写成已落地事实。

## 新窗口执行规则

1. 先读根目录 `AGENTS.md`、`README.md`、`docs/progress.md` 和本任务卡。
2. 阅读 PRD：[agent-memory-query-polish.md](../prd/agent-memory-query-polish.md)。
3. 核对任务 76、77、78、79 已完成；未完成则停止。
4. 对比当前模型和 reasoning 与本节建议；如果不一致或未知，先告诉用户建议配置并等待确认，除非用户明确要求继续。
5. 只做文档最终对齐，不引入新的运行时代码。
6. 按本任务验证计划核对文档与代码。
7. 测试/检查通过后更新 `docs/progress.md`；不要自动 push，除非用户明确要求。

## 依赖

76、77、78、79

## 背景

memory_query 润色完成后，README 才能从当前 `memory_query_reply -> post_turn_jobs` 更新为实际运行的 `memory_query_reply -> memory_query_polish -> post_turn_jobs`。本任务负责把 PRD 目标状态和代码实际状态对齐到文档 source of truth。

## 目标

- README 同步当前运行 graph、路径规则、配置和验证命令。
- docs/maps 更新 memory_query polish 入口、状态字段、LLM 调用和 failure modes。
- PRD 补充落地状态与偏差。
- docs/progress 标记 76-80 全部完成。
- 移除 README 中任何“未落地预览”措辞，改成当前事实。

## 范围

| 模块 | 变更 |
|------|------|
| `README.md` | 更新 graph Mermaid、单轮流水线、memory_query 路径规则、环境变量表、验证命令 |
| `docs/maps/chat-turn-pipeline.md` | 增加 `memory_query_polish` 导航 |
| `docs/maps/llm-calls.md` | 增加 `MEMORY_QUERY_POLISH` 小模型用途 |
| `docs/maps/state-fields.md` | 如新增 state 字段，补充说明 |
| `docs/maps/failure-modes.md` | 增加 polish 失败回退 |
| `docs/prd/agent-memory-query-polish.md` | 补充落地状态、偏差和最终链路 |
| `docs/progress.md` | 任务 80 状态、总览、changelog |

## 验证方案

```bash
rg -n "memory_query_polish|MEMORY_QUERY_POLISH|memory_query.polish" README.md docs agent/src agent/tests agent/evals
rg -n "未落地|方案预览" README.md
cd agent && uv run pytest tests/test_graph_compile.py tests/test_memory_query_polish.py tests/test_memory_query_executor.py tests/test_path_contract.py -v
cd agent && uv run ruff check src tests scripts
```

## 非范围

- 不新增运行时代码。
- 不调整小模型 prompt。
- 不改文档治理顺序。

## 完成标准

- [ ] README 只描述已落地当前事实。
- [ ] docs/maps 指向真实实现和测试入口。
- [ ] PRD 明确已完成项和偏差。
- [ ] progress 76-80 全部完成，当前建议下一步回到产品需求规划。

## 进度更新

`docs/progress.md` **80** → 实现完成后改为 `✅`；总览改为 80/80 已完成。
