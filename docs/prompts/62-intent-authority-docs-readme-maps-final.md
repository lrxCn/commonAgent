# 62 - 意图权威收敛 Phase 4：README、代码地图与文档最终对齐

## 建议执行模型

- 模型：GPT-5.4
- Reasoning：medium
- 原因：这是意图权威来源收敛的文档收口任务，需要核对已落地代码、README 当前契约、PRD、任务卡、代码地图和进度表，防止文档继续描述双轨权威。

## 新窗口执行规则

1. 先读根目录 `AGENTS.md`、`README.md`、`docs/progress.md` 和本任务卡。
2. 核对 `docs/progress.md` 中本任务依赖是否完成；未完成则停止。
3. 对比当前模型和 reasoning 与本节建议；如果不一致或未知，先告诉用户建议配置并等待确认，除非用户明确要求继续。
4. 只实现本任务范围，不顺手做相邻任务。
5. 按本任务测试计划验证。
6. 测试通过后更新 `docs/progress.md`。

## 依赖

61

## 背景

任务 58-61 完成后，运行时意图权威来源应从“双轨分类 + conflict 观测”收敛为“`IntentDecision` 单源 + `turn_type` 兼容派生”。根据根目录 `AGENTS.md`，这种架构、状态/context、RAG flow、观测语义变化必须同步文档。

## 目标

- README 描述新的当前事实：`IntentDecision` 是唯一权威来源，`turn_type` 是兼容派生字段。
- `docs/maps/` 更新主图、状态字段、RAG flow、控制面、failure modes 相关描述。
- `docs/prd/agent-intent-authority-consolidation.md` 补充落地状态与偏差说明。
- `docs/progress.md` 标记任务 58-62 收口。
- 复核文档治理顺序不变。

## 范围

| 模块 | 变更 |
|------|------|
| `README.md` | 同步单源 intent authority、运行流水线、验证入口 |
| `docs/maps/control-plane.md` | 更新 `IntentDecision` 单源与 `graph.turn_type` adapter |
| `docs/maps/chat-turn-pipeline.md` | 更新 `load_memory` 分类阶段 |
| `docs/maps/state-fields.md` | 更新 `turn_type` / `intent_decision` 生命周期 |
| `docs/maps/rag-flow.md` | 明确 RAG 读取派生 `turn_type`，不是旧全局分类 |
| `docs/maps/failure-modes.md` | 如 conflict/fallback 语义变化，更新说明 |
| `docs/prd/agent-intent-authority-consolidation.md` | 补充落地状态和偏差 |
| `docs/progress.md` | 本任务状态和最终变更日志 |

## 文档原则

- README 只写当前已落地事实。
- PRD 保留设计意图和历史，不覆盖 README。
- docs/maps 只回答维护问题，指向实现和测试入口，不引入新契约。
- 不改变根 `AGENTS.md` 文档治理顺序，除非用户明确批准。

## 验证方案

```bash
rg -n "IntentDecision|turn_type|classify_turn_type|classify_intent|单源|唯一权威|兼容派生" README.md docs/maps docs/prd docs/progress.md
rg -n "双轨|shadow|intent_conflict|legacy_turn_type|rag/intent.py|is_user_fact_statement" README.md docs/maps docs/prd docs/prompts
rg -n "文档秩序|Source Of Truth|source of truth|用户同意|approval" AGENTS.md README.md docs
rg -n "TODO|待补|旧结构|未来会" README.md docs/maps docs/progress.md
```

如项目已有 Markdown lint，可额外运行；没有则人工检查链接、路径和文档层级。

## 非范围

- 不新增运行时功能。
- 不改业务代码，除非发现文档引用的实现入口已经不存在且必须修复路径。
- 不删除历史 PRD。
- 不改变根 `AGENTS.md` 治理规则。

## 完成标准

- [ ] README 描述单源意图权威当前事实。
- [ ] docs/maps 指向新的实现和测试入口。
- [ ] progress 任务 58-62 状态与变更日志完整。
- [ ] PRD 与 README 的关系清楚。
- [ ] 文档中没有把旧双轨权威写成当前事实。
- [ ] 文档治理顺序与根 `AGENTS.md` 一致。

## 进度更新

`docs/progress.md` **62** → 实现完成后改为 `✅`。
