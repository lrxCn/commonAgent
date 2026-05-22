# 50 - 控制面 Phase 1：Signals 与确定性 Intent Engine

## 建议执行模型

- 模型：GPT-5.5
- Reasoning：high
- 原因：本任务重建确定性意图识别核心，需要把旧启发式规则降级为 signal，并保证高置信规则不误触发副作用路径。

## 依赖

49

## 背景

控制面 PRD 要求顶级意图识别采用级联：

```text
Normalize
  -> Signal Extraction
  -> Deterministic High-Confidence Rules
  -> LLM Structured Classifier
  -> Confidence / Conflict Check
  -> Policy Gate
  -> Route
```

本任务只实现前半段：normalize、signal extraction、确定性高置信规则和 `classify_intent()` 的纯逻辑入口。不接入 LLM，不改变 graph 行为。

## 目标

- 新增 `agent/src/intent/` 包。
- 抽取疑问词、第一人称、公司自指、事实属性、明确值、工具动作、指代、安全信号等 signals。
- 实现高置信规则：事实写入、记忆查询、知识库查询、客户端动作、寒暄、模糊指代、普通聊天。
- 将旧 `rag.intent.is_user_fact_statement()` 从全局路由职责降级为事实写入 signal 的参考规则。
- 明确「我是谁」「我叫什么」「我的名字是什么」「我公司在哪」必须是 `memory_query`。

## 范围

| 模块 | 变更 |
|------|------|
| `agent/src/intent/__init__.py` | 导出新 intent API |
| `agent/src/intent/signals.py` | `IntentSignals`、normalize、信号抽取 |
| `agent/src/intent/rules.py` | 高置信规则决策 |
| `agent/src/intent/engine.py` | `classify_intent()` 纯逻辑入口 |
| `agent/src/rag/intent.py` | 保持兼容导出，但不再作为新控制面的权威入口 |
| `agent/tests/test_intent_signals.py` | 覆盖 signal extraction |
| `agent/tests/test_intent_rules.py` | 覆盖确定性高置信分类 |
| `agent/tests/test_turn_type.py` | 如需补反例，确保旧测试与新契约关系清楚 |
| `docs/progress.md` | 本任务状态 |

## 规则要求

必须正确分类：

| 输入 | route | 说明 |
|------|-------|------|
| 我叫张三 | `fact_update` | 明确属性和值 |
| 我的名字是张三 | `fact_update` | 明确属性和值 |
| 我公司在天翔街188号 | `fact_update` | 公司记忆写入 |
| 我是谁 | `memory_query` | 第一人称记忆查询 |
| 我叫什么 | `memory_query` | 第一人称记忆查询 |
| 我的名字是什么 | `memory_query` | 第一人称记忆查询 |
| 我公司在哪 | `memory_query` | 公司记忆查询 |
| 报销制度是什么 | `knowledge_query` | 知识库查询 |
| 它需要什么材料 | `ambiguous` | 指代/承接 |
| 你好 | `chitchat` | 寒暄 |

## 冲突原则

- 有疑问词或疑问标记时，不允许直接输出 `operation=memory_write`。
- `memory_write` 必须有明确属性和值。
- 不确定时输出低置信 `general_chat` 或 `ambiguous`，不得强判 `fact_update`。
- 规则只处理高置信场景，不为了提高召回牺牲误判率。

## 非范围

- 不调用 LLM。
- 不接入 LangGraph。
- 不改变 `turn_type` 当前写入方式。
- 不接管 fast path。
- 不新增 `memory_query` executor。
- 不更新 README 当前运行契约。

## 测试方案

```bash
cd agent
uv run pytest tests/test_intent_contracts.py tests/test_intent_signals.py tests/test_intent_rules.py -v
uv run pytest tests/test_turn_type.py tests/test_rag_router.py tests/test_rewrite.py -v
uv run ruff check src tests
```

## 完成标准

- [ ] `classify_intent()` 可独立于 LangGraph 单测。
- [ ] 第一人称疑问反例全部进入 `memory_query` 或低风险保守路径，不进入 `fact_update`。
- [ ] 事实写入正例仍能高置信进入 `fact_update`。
- [ ] 旧 `rag.intent` 兼容导出不破坏现有测试。
- [ ] 本任务不改变线上 graph 行为。
- [ ] `docs/progress.md` 同步。

## 进度更新

`docs/progress.md` **50** → 实现完成后改为 `✅`。
