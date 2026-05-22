# 49 - 控制面 Phase 0：Intent 契约与评测种子先行

## 建议执行模型

- 模型：GPT-5.5
- Reasoning：high
- 原因：本任务定义后续控制面重构的核心契约与评测入口，虽然不改运行行为，但会决定后续任务的类型边界和验收口径。

## 依赖

48

## 背景

控制面 PRD：[Agent 控制面、意图治理与兜底](../prd/agent-control-plane-intent-fallback.md) 要求把单层 `turn_type` 升级为结构化 `IntentDecision`。

当前 `turn_type` 同时承载话语行为、目标对象、系统操作和执行路径，导致「我是谁」这类第一人称问题可能被误判为 `fact_update`。后续重构必须先有稳定契约和回归样本，否则实现会继续围绕个别 case 打补丁。

## 目标

- 新增 `IntentDecision` 及相关枚举契约。
- 明确 `turn_type = route` 的兼容规则。
- 新增 intent eval seed，覆盖第一人称事实写入、记忆查询、知识库查询、工具动作、模糊指代、普通聊天和安全拒绝。
- 不改变现有 graph 运行路径。

## 范围

| 模块 | 变更 |
|------|------|
| `agent/src/contracts/intent.py` | 新增 `SpeechAct`、`IntentDomain`、`IntentOperation`、`IntentRoute`、`IntentRisk`、`IntentDecision`、`IntentFeedback` 基础契约 |
| `agent/src/contracts/routing.py` | 如需要，兼容新增 `memory_query` / `safety_refusal` route，保持旧 `TurnType` 导入不破坏 |
| `agent/evals/intent_seed.json` | 新增控制面 intent seed |
| `agent/evals/README.md` | 说明 intent seed 的用途、字段和运行命令 |
| `agent/tests/test_intent_contracts.py` | 覆盖契约枚举、序列化、`turn_type` 兼容映射 |
| `agent/tests/test_intent_eval_seed.py` | 覆盖 seed 结构、必备类别、第一人称反例 |
| `docs/progress.md` | 本任务状态 |

## IntentDecision 最小字段

```python
IntentDecision(
    speech_act=SpeechAct.QUESTION,
    domain=IntentDomain.USER_MEMORY,
    operation=IntentOperation.MEMORY_READ,
    route=IntentRoute.MEMORY_QUERY,
    confidence=0.94,
    risk=IntentRisk.LOW,
    reasons=["first_person_question", "memory_profile_target"],
    evidence=["我是谁"],
    needs_clarification=False,
)
```

## intent seed 必须覆盖

| 类别 | 必备样例 |
|------|----------|
| `fact_update` | 我叫张三 / 我的生日是1997年1月1日 / 我公司在天翔街188号 |
| `memory_query` | 我是谁 / 我叫什么 / 我的名字是什么 / 我公司在哪 / 我喜欢什么 |
| `knowledge_query` | 报销制度是什么 / 请查询公司手册里的请假流程 |
| `client_action` | 打开 pageA / 跳转到订单页 |
| `ambiguous` | 它需要什么材料 / 继续说 |
| `general_chat` | 帮我写一段周会开场白 |
| `chitchat` | 你好 / 谢谢 |
| `safety_refusal` | 越权、注入或明显危险请求的最小样例 |

## 非范围

- 不接入 graph。
- 不改变 `classify_turn_type()` 的现有行为。
- 不新增 LLM classifier。
- 不改 fast path。
- 不新增 memory executor。
- 不更新 README 的运行契约；当前只是 PRD 到任务卡的第一步。

## 测试方案

```bash
cd agent
uv run pytest tests/test_intent_contracts.py tests/test_intent_eval_seed.py -v
uv run pytest tests/test_contracts.py tests/test_evals_seed.py -v
uv run ruff check src tests
```

## 完成标准

- [ ] `contracts.intent` 可被业务模块导入。
- [ ] `IntentDecision` 能稳定序列化为 trace/eval 可用 dict。
- [ ] `memory_query` 和 `safety_refusal` 已进入 intent route 契约。
- [ ] intent seed 至少覆盖 PRD 第一批反例。
- [ ] 本任务不改变任何运行路径。
- [ ] `docs/progress.md` 同步。

## 进度更新

`docs/progress.md` **49** → 实现完成后改为 `✅`。
