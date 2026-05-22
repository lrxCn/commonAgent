# 57 - 控制面 Phase 8：README、代码地图与文档治理最终对齐

## 建议执行模型

- 模型：GPT-5.4
- Reasoning：medium
- 原因：这是控制面路线的文档收口任务，需要核对已落地代码、README 当前契约、PRD 草案、任务卡、代码地图和进度表，防止文档描述未来状态或遗漏新运行边界。

## 依赖

56

## 背景

任务 49-56 完成后，控制面能力会从 PRD 逐步落入运行时：`IntentDecision`、Intent Engine、Policy Gate、`memory_query`、Fallback Manager、Feedback/Eval。根据根目录 `AGENTS.md`，当任务改变架构、状态/context 规则、memory 语义、RAG flow、`client_actions` 或文档治理时，必须同步更新相关文档。

本任务是控制面路线的最后一个任务：更新项目中该更新的各种文档，并复核文档层级一致。

## 目标

- README 同步当前真实控制面架构和运行契约。
- `docs/maps/` 新增或更新控制面相关地图。
- `docs/progress.md` 完整记录任务完成状态和变更日志。
- `docs/prd/agent-control-plane-intent-fallback.md` 保持为设计草案/历史说明，不覆盖 README 当前事实。
- 复核 `AGENTS.md`、README、progress、prompts、PRD、maps 的文档治理顺序。
- 如果需要改变 AI 工作规则或文档治理规则，必须先向用户说明问题、替代规则、收益和风险并取得同意。

## 范围

| 模块 | 变更 |
|------|------|
| `README.md` | 同步 IntentDecision、Policy Gate、memory_query、Fallback Manager、Feedback/Eval、运行流水线和验证命令 |
| `docs/maps/chat-turn-pipeline.md` | 更新控制面阶段：intent classify、policy gate、executor router、fallback |
| `docs/maps/state-fields.md` | 增加 intent/policy/fallback 单轮字段生命周期 |
| `docs/maps/llm-calls.md` | 增加 `INTENT_CLASSIFIER` 用途、timeout、fallback |
| `docs/maps/rag-flow.md` | 明确 RAG 由 intent/policy 决定，不再由 `rag/intent.py` 全局掌权 |
| `docs/maps/client-actions.md` | 更新工具动作由 intent + policy + whitelist 共同约束 |
| `docs/maps/failure-modes.md` | 更新 Agent 级 fallback 策略 |
| `docs/maps/control-plane.md` | 如有必要，新增控制面专门地图 |
| `docs/prd/agent-control-plane-intent-fallback.md` | 如实现与 PRD 有差异，补充“落地状态/偏差说明” |
| `docs/progress.md` | 本任务状态和控制面路线收口日志 |

## 文档原则

- README 只写当前已落地事实，不提前描述未实现功能。
- PRD 可以保留设计意图、历史决策和未来计划。
- docs/maps 回答维护问题，链接实现和测试入口，不引入新契约。
- 不重复大段 PRD 内容到 README。
- 不静默改变文档秩序或 AI 工作规则。

## 验证方案

```bash
rg -n "IntentDecision|memory_query|Policy Gate|Fallback|intent_seed|INTENT_CLASSIFIER" README.md docs agent/evals
rg -n "rag/intent.py|is_user_fact_statement|turn_type|memory_query" README.md docs/maps docs/prd docs/prompts
rg -n "文档秩序|Source Of Truth|source of truth|用户同意|approval" AGENTS.md README.md docs
rg -n "TODO|待补|旧结构|未来会" README.md docs/maps docs/progress.md
```

如项目已有 Markdown lint，可额外运行；没有则人工检查链接、路径和文档层级。

## 非范围

- 不新增运行时功能。
- 不改业务代码，除非发现文档引用的实现入口已经不存在且必须修复路径。
- 不删除历史 PRD。
- 不改变根 `AGENTS.md` 治理规则，除非用户明确批准。

## 完成标准

- [ ] README 描述控制面当前真实架构。
- [ ] docs/maps 能指向 intent、policy、memory_query、fallback、feedback 的实现和测试入口。
- [ ] progress 任务 49-57 状态与变更日志完整。
- [ ] PRD 与 README 的关系清楚：PRD 是设计草案/历史，README 是当前运行契约。
- [ ] 文档中没有把未落地功能写成当前事实。
- [ ] 文档治理顺序与根 `AGENTS.md` 一致。

## 进度更新

`docs/progress.md` **57** → 实现完成后改为 `✅`。
