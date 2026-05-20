# 26 - Query Rewrite 条件跳过（降延迟）

## 依赖

09, 10, 25

## 背景与动机

任务 **09** 起，主图 **每轮** 在 `rewrite` 节点调用一次 LLM（`rewrite.txt` + mem0 + 近期对话），产出 `rewritten_query`，再进入 RAG 路由与检索。

实测与架构复盘结论：

- **Token 成本**可接受（小模型 + 短 prompt），但 **端到端延迟**敏感：rewrite 在关键路径上且 **阻塞** 后续 `rag_router` / `retrieve` / 首 token。
- 大量轮次 **不需要** 消解指代即可检索或对话，例如：寒暄（`router.is_chitchat`）、自包含 FAQ 问句、无近期上下文的完整长问。
- `rewrite.txt` 已约定「原问题清晰可原样输出」，但当前实现仍 **先调 LLM 再得到原句**，无法节省 RTT。

本任务在 **不改变** `load_memory → rewrite → rag_router` 图顺序的前提下，在 **rewrite 节点内部** 增加 **零 LLM** 的 `should_rewrite` 判断；跳过时不调用改写模型，`rewritten_query = trim(user_message)`。

> 任务 **09**、**10** 语义不变：下游仍只读 `rewritten_query`；**不修改** `09-*.md`、`10-*.md` 原文，以本文为准描述 rewrite 演进。

## 目标

- 新增 **`should_rewrite(...)`**（纯函数、可单测）：基于规则判断本轮是否值得调用改写 LLM。
- **`rewrite_node`**：先 `should_rewrite`；若为 `False`，**不** `_invoke_llm`，直接写 `rewritten_query`；若为 `True`，走现有 `rewrite_query` 路径。
- **首要 KPI**：降低 rewrite LLM **调用率**与 P95 **rewrite 节点耗时**；token 节省为副产品。
- LangSmith rewrite span metadata 可区分 **skipped / invoked** 及跳过原因（便于上线后调规则）。

## 范围

| 模块 | 变更 |
|------|------|
| `agent/src/rag/rewrite.py` | `should_rewrite`；`rewrite_node` 分支；可选 `rewrite_skip_reason` 仅用于 tracing |
| `agent/src/rag/router.py` 或 `agent/src/rag/intent.py` | **复用** `is_chitchat`（避免循环 import 时可抽到 `rag/intent.py`） |
| `agent/src/settings/config.py` | `REWRITE_SKIP_ENABLED`（默认 `true`）；可选 `REWRITE_FORCE` 调试开关 |
| `agent/.env.example` | 上述配置项（掩码说明） |
| `agent/src/observability/tracing.py` | rewrite metadata：`rewrite_skipped`、`rewrite_skip_reason` |
| `agent/tests/test_rewrite.py` | 跳过/不跳过用例；问候不调 mock LLM |
| `agent/tests/test_graph_invoke_mock.py` | 可选：问候轮 mock LLM 未被调用（若可注入计数） |
| `docs/architecture.md` §5、§6 | 条件 rewrite 目标态 |
| `docs/progress.md` | 本任务行 |
| `agent/README.md` | LangSmith 查看说明补一句 |

## 非范围

- **不** 调整主图边顺序（不做「先 rag_router 再 lazy rewrite」；留作后期任务）。
- **不** 合并 rewrite + rag_router 为单次 LLM（任务卡后期可选）。
- **不** 修改 RAG 检索算法、Supervisor、mem0 读/写。
- **不** 用 rewrite 跳过替代 `rag_router` 的 SKIP（二者正交：跳过 rewrite 仍可能 `need_rag=true`）。

## 需求规格：`should_rewrite`

### 输入（建议签名）

```python
def should_rewrite(
    user_message: str,
    *,
    recent_messages: Sequence[BaseMessage],
    mem0_memories: Sequence[str] | None = None,
) -> tuple[bool, str]:
    """Return (need_llm_rewrite, reason_code). reason_code for tracing only."""
```

### 输出约定

| `need_llm_rewrite` | `rewritten_query` | 说明 |
|--------------------|-------------------|------|
| `False` | `user_message.strip()` | **禁止** 调用改写 LLM |
| `True` | LLM 输出（失败回退原文） | 与现行为一致 |

### 规则（第一期，确定性、零 LLM）

按 **自上而下** 匹配，命中即返回 `(False, reason_code)`：

| 优先级 | 条件 | `reason_code` | 说明 |
|--------|------|---------------|------|
| R0 | `REWRITE_SKIP_ENABLED=false` | — | 全员走 LLM（兼容旧行为 / A-B） |
| R1 | `is_chitchat(user_message)` | `chitchat` | 与 `router.py` 问候/致谢正则一致 |
| R2 | 无 `recent_messages`（本轮前无对话，或仅当前 human）**且** 无 mem0 事实 | `standalone_no_context` | 首句自包含场景 |
| R3 | 用户句 **无指代/承接** 启发式 **且** 长度 ≥ N（建议 N=8）**且**（可选）`has_knowledge_intent(user_message)` | `self_contained` | 清晰 FAQ，可直接检索 |

**需要 LLM 改写**（返回 `(True, "needs_disambiguation")`）建议包括：

- 含指代/承接词：如 `它`、`这个`、`那个`、`上述`、`刚才`、`继续`、`还有吗` 等（维护 `_ANAPHORA_RE` 或列表）。
- 短句（长度 &lt; N）且存在 `recent_messages` 或 mem0（需结合上下文才完整）。
- R1–R3 均未命中时的 **默认保守策略**：第一期建议 **`True`**（宁可多调一次 LLM，避免漏消解）；上线后根据 LangSmith `rewrite_skipped` 与检索指标再收紧 R3。

> **实现注意**：R2/R3 与 `has_knowledge_intent` 均来自 `router.py` 时，抽公共模块 `rag/intent.py` 或 `rewrite` 内 import 同级函数，**禁止** `rewrite` ↔ `router` 循环依赖。

### 配置

| 变量 | 默认 | 说明 |
|------|------|------|
| `REWRITE_SKIP_ENABLED` | `true` | `false` 时关闭跳过，每轮仍调 LLM |
| `REWRITE_MIN_SELF_CONTAINED_LEN` | `8` | R3 最短字符数（可选） |

## 实现要点

### 1. `rewrite_node` 伪代码

```text
if not settings.REWRITE_SKIP_ENABLED:
    return llm_rewrite(...)

need, reason = should_rewrite(user_message, recent_messages=..., mem0_memories=...)
if not need:
    return {"rewritten_query": user_message.strip()}  # tracing: skipped, reason

return {"rewritten_query": rewrite_query(...)}  # tracing: invoked
```

### 2. 与 `rag_router` 的关系

- 跳过 rewrite 时 `rewritten_query` 可能仍等于原文；`is_chitchat(message, rewritten_query)` 在 router 仍应能 SKIP RAG。
- **不要** 假设「跳过 rewrite ⇒ 一定不检索」。

### 3. 观测

`rewrite` span metadata 建议字段：

- `rewrite_skipped`: `true` / `false`
- `rewrite_skip_reason`: `chitchat` | `standalone_no_context` | `self_contained` | `""`（invoked 时为空）
- 保留现有 `mem0_facts_count`、`mem0_text_len`（仅 invoked 时非零亦可）

### 4. 性能原则（文档）

rewrite 跳过仅减少 **一次 LLM RTT**；`rag_router` hybrid 不确定时仍可能有第二次小模型，本任务 **不** 处理。

## 测试方案

```bash
cd agent
uv run pytest tests/test_rewrite.py tests/test_rag_router.py tests/test_graph_invoke_mock.py -v
```

| 用例 | 期望 |
|------|------|
| `should_rewrite("你好", ...)` | `(False, "chitchat")`；mock LLM **0** 次 |
| `should_rewrite("公司报销流程是什么", 无 recent, 无 mem0)` | `(False, "standalone_no_context")` 或按 R3 设计 |
| `should_rewrite("它怎么办", recent=含报销对话)` | `(True, ...)`；mock LLM **1** 次 |
| `REWRITE_SKIP_ENABLED=false` | 问候也调用 LLM（与旧行为一致） |
| `rewrite_node` 跳过 | `rewritten_query == user_message`（或等价 trim） |

## 完成标准

- [ ] `should_rewrite` 可单测且覆盖上表。
- [ ] 问候类轮次 rewrite span 显示 `rewrite_skipped=true`，端到端少一次 LLM 调用。
- [ ] `architecture.md` §5/§6、`agent/README.md`、`progress.md` 任务 26 标为 ✅。
- [ ] `.env.example` 含 `REWRITE_SKIP_ENABLED`。

## 验证清单（手工）

1. LangSmith：`message=你好` → rewrite 节点耗时接近 0（无子 LLM span），`rewrite_skipped=true`。
2. 多轮：`报销流程是什么` → `它需要什么材料` → 第二轮 `rewrite_skipped=false` 且改写含「报销」。
3. 对比同 thread 连续两轮 P95：跳过轮次 `load_memory→supervisor` 段延迟明显下降。

## 后期可选（本任务不做）

- 默认 `(True)` 改为更激进的「仅指代才 rewrite」。
- `rewrite → rag_router` 合并为单次结构化 LLM。
- 将 `should_rewrite` 结果写入 `AgentState` 键 `rewrite_skipped`（本期仅 tracing 即可）。

## 进度更新

`docs/progress.md` **26** → 实现完成后改为 `✅`。
