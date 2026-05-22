---
name: Agent Control Plane, Intent Governance and Fallback
overview: 面向长期可维护 Agent 的控制面 PRD 草案：重建意图识别、策略闸门、执行器路由、系统级兜底与反馈闭环。
isProject: false
---

# Agent 控制面、意图治理与兜底（PRD 草案）

## 文档定位

本文是下一阶段控制面重构的设计草案，不替代当前 [README.md](../../README.md) 的运行契约，也不表示现有实现需要立即整体重写。

当前系统已经具备 checkpoint、mem0、RAG、client_actions、deepagents、SSE、LangSmith tracing 和路径契约等能力。真实问题不在单个能力层，而在能力层上方缺少一个足够强的控制面：谁判断用户要什么，谁决定允许走什么路径，失败时如何降级，用户纠错如何进入评测闭环。

本文目标是把这层设计清楚，使后续任务不再围绕单个误判打补丁。

## 背景

一次真实问题暴露了控制面短板：

```text
用户：我是谁
系统判定：
turn_type = fact_update
turn_type_reason = fact_statement_rule
```

直接原因是旧规则把「我 + 是」当成事实陈述信号，而疑问检测没有覆盖「谁」。但根因不是少了一个疑问词，而是当前系统把多个维度压成了一个 `turn_type`：

- 用户是在陈述、提问、命令，还是寒暄。
- 用户目标对象是个人记忆、企业知识库、客户端工具，还是普通对话。
- 系统应该读记忆、写记忆、检索 RAG、产出工具动作，还是生成开放回答。
- 当前路径是否允许 fast path，失败时是否需要澄清、降级、拒绝或人工介入。

当一个粗粒度 `turn_type` 拥有路径闸门权力时，简单规则误判会直接造成系统级后果：

- 错误跳过 rewrite、RAG、Supervisor。
- 错误返回模板确认。
- 错误调度 mem0 写入。
- trace 看起来像正常 fast path，实际语义已经失败。

这说明 `rag/intent.py` 里的启发式规则已经承担了过高职责。RAG 是能力层，不应该拥有全局意图识别和路由治理权。

## 核心判断

Agent 应拆成两层：

```text
控制面 Control Plane
  判断、授权、路由、兜底、反馈

能力面 Capability Plane
  记忆、RAG、client_actions、deepagents、普通生成、SSE
```

当前 mem0、RAG、client_actions、deepagents 仍有价值。真正需要重建的是控制面，而不是一次性废弃所有能力层。

## 目标

1. 建立结构化意图识别，不再让单个正则或单个 `turn_type` 直接决定执行路径。
2. 把 `turn_type` 从唯一事实来源降级为兼容路由字段，由完整 `IntentDecision` 推导。
3. 明确区分记忆写入和记忆查询，让「我是谁」「我叫什么」「我公司在哪」走 `memory_query`。
4. 重新定义 fast path 准入制度，使事实写入宁可漏判，不可误判。
5. 建立 Agent 级兜底机制，每一层失败都有明确降级、澄清、拒绝、重试或人工介入策略。
6. 将 deepagents / ReAct 定位为复杂任务 executor，而不是全局兜底。
7. 建立反馈闭环，让线上误判进入 LangSmith Dataset、本地 eval 和回归测试。
8. 让未来所有路径变化能通过 intent eval、path eval、memory eval 和 tool eval 验收。

## 非目标

- 不改变 Front -> Back -> Agent 三层边界。
- 不让浏览器直连 Agent。
- 不把客户端 `client_actions` 改成 Agent 服务端工具执行。
- 不取消 mem0、RAG、LangGraph、deepagents。
- 不把所有输入都交给大模型分类。
- 不把 deepagents 当作兜底万能执行器。
- 不在本文中直接规定具体任务拆分和排期。

## 设计原则

### 控制面优先

能力层越强，越需要控制面约束。长期记忆、工具动作、RAG 引用和 deepagents 规划都不能由弱规则直接触发。

### 不确定就降权

低置信 intent 不能触发 fast path、memory write、外部动作或高风险工具。应进入澄清、保守 executor 或拒绝路径。

### 缺证据就明说

记忆没有查到就是没有查到，RAG 没召回就是没找到来源，工具不可用就是不可用。不得用模型常识填补系统证据缺口。

### 有副作用就审批

任何会写记忆、执行工具、修改外部状态或暴露敏感信息的路径，都必须经过策略闸门。高风险动作需要 human-in-the-loop。

### 失败必须反馈

每次 fallback、误判、用户纠错都应被结构化记录，进入 eval 数据集和回归测试。

## IntentDecision 契约

新增完整结构化意图结果，`turn_type` 只作为兼容字段由 `route` 推导。

```python
IntentDecision(
    speech_act="question",
    domain="user_memory",
    operation="memory_read",
    route="memory_query",
    confidence=0.94,
    risk="low",
    reasons=["first_person_question", "memory_profile_target"],
    evidence=["我是谁"],
    needs_clarification=False,
)
```

建议枚举：

| 字段 | 候选值 | 说明 |
|------|--------|------|
| `speech_act` | `statement` / `question` / `command` / `chitchat` / `unsafe` / `unclear` | 用户话语行为 |
| `domain` | `user_memory` / `org_memory` / `knowledge_base` / `client_tool` / `open_chat` / `safety` / `unknown` | 用户目标对象 |
| `operation` | `memory_write` / `memory_read` / `kb_retrieve` / `client_action` / `answer` / `clarify` / `reject` | 系统应执行的操作 |
| `route` | `fact_update` / `memory_query` / `knowledge_query` / `client_action` / `chitchat` / `ambiguous` / `general_chat` / `safety_refusal` | 最终路由 |
| `confidence` | `0.0 - 1.0` | 分类置信度 |
| `risk` | `low` / `medium` / `high` | 误判或执行风险 |
| `reasons` | `list[str]` | 稳定 reason code |
| `evidence` | `list[str]` | 支持分类的原文片段或信号 |
| `needs_clarification` | `bool` | 是否需要用户澄清 |

兼容规则：

```text
turn_type = IntentDecision.route
turn_type_reason = first(IntentDecision.reasons)
```

## 目标示例

| 输入 | speech_act | domain | operation | route |
|------|------------|--------|-----------|-------|
| 我叫李雷 | `statement` | `user_memory` | `memory_write` | `fact_update` |
| 我的生日是1997年1月1日 | `statement` | `user_memory` | `memory_write` | `fact_update` |
| 我公司在天翔街188号 | `statement` | `org_memory` | `memory_write` | `fact_update` |
| 我是谁 | `question` | `user_memory` | `memory_read` | `memory_query` |
| 我叫什么 | `question` | `user_memory` | `memory_read` | `memory_query` |
| 我的名字是什么 | `question` | `user_memory` | `memory_read` | `memory_query` |
| 我公司在哪 | `question` | `org_memory` | `memory_read` | `memory_query` |
| 报销制度是什么 | `question` | `knowledge_base` | `kb_retrieve` | `knowledge_query` |
| 它需要什么材料 | `question` | `unknown` | `clarify` 或 `kb_retrieve` after rewrite | `ambiguous` |
| 打开 pageA | `command` | `client_tool` | `client_action` | `client_action` |
| 帮我写一段周会开场白 | `command` | `open_chat` | `answer` | `general_chat` |

## 级联识别流程

顶级意图识别不应依赖单一正则，也不应默认调用模型。采用级联：

```text
Normalize
  -> Signal Extraction
  -> Deterministic High-Confidence Rules
  -> LLM Structured Classifier
  -> Confidence / Conflict Check
  -> Policy Gate
  -> Route
```

### Normalize

负责标准化输入：

- 去除首尾空白。
- 标准化中英文标点。
- 保留原文用于 evidence。
- 不做会改变事实的改写。

### Signal Extraction

只抽取信号，不决定最终路径：

| 信号 | 示例 |
|------|------|
| `has_question_word` | 谁、什么、哪、哪里、多少、几、怎么、为什么、是否、能不能、有没有 |
| `has_question_mark` | `?`、`？` |
| `first_person` | 我、我的、本人、咱、俺 |
| `org_self_reference` | 我公司、我们公司、单位 |
| `fact_attribute` | 姓名、生日、地址、职业、偏好、公司 |
| `explicit_value` | 具体姓名、日期、地点、数字、邮箱、手机号、偏好值 |
| `command_verb` | 打开、跳转、查询、创建、删除、发送 |
| `tool_reference` | 工具名、页面名、动作名 |
| `anaphora` | 它、这个、那个、上述、刚才、继续 |
| `unsafe_signal` | 注入、越权、危险动作、敏感信息请求 |

旧 `is_user_fact_statement()` 应降级为信号提取的一部分，例如：

```text
signals.has_fact_write_pattern = true
```

它不能直接决定 `route=fact_update`。

### Deterministic Rules

规则只处理高置信场景：

```text
明显寒暄 -> chitchat
明确事实写入 -> fact_update
明确记忆查询 -> memory_query
明确知识库问题 -> knowledge_query
明确客户端工具动作 -> client_action
明确安全拒绝 -> safety_refusal
```

规则一旦发现冲突，不做强判，交给后续 classifier 或 policy。

### LLM Structured Classifier

仅在规则无法高置信判断或信号冲突时调用小模型，输出结构化 schema。

要求：

- 使用 Pydantic / JSON schema 校验。
- 禁止自然语言解析。
- 必须输出 `confidence`、`reasons`、`evidence`。
- 模型输出不能直接执行，由 Policy Gate 再裁决。

### Confidence / Conflict Check

常见冲突：

| 冲突 | 处理 |
|------|------|
| 有疑问词，但规则命中事实写入 | 禁止 fact_update fast path |
| 模型判 memory_write，但没有明确 value | 禁止 memory_write |
| 工具动作命中，但工具不在白名单 | 降级为工具不可用回复 |
| RAG 问题无知识库域证据 | 允许澄清或普通回答，但不得伪造引用 |
| 高风险工具 + 低置信 | 停止并要求确认或拒绝 |

## Policy Gate

Policy Gate 是控制面核心。它不负责识别意图，只负责判断某个 intent 是否允许进入某条路径。

### fast path 准入

`fact_update` fast path 必须同时满足：

```text
speech_act == statement
operation == memory_write
confidence >= 0.9
risk == low
has_explicit_attribute == true
has_explicit_value == true
no_question_signal == true
```

允许：

```text
我叫张三
我的名字是张三
我的生日是1997年1月1日
我公司在天翔街188号
我喜欢简洁一点的回答
```

禁止：

```text
我是谁
我叫什么
我的名字是什么
我公司在哪
我喜欢什么
我是做什么的
你知道我是谁吗
```

原则：

```text
memory_write 宁可漏判，不可误判。
```

漏判的代价是多走一次 executor。误判的代价是错误确认、错误写入、错误跳过下游能力。

### memory_query 准入

以下输入应进入 `memory_query`：

```text
我是谁
我叫什么
我的名字是什么
我的生日是什么
我多大
我在哪里工作
我公司在哪
我喜欢什么
你知道我是谁吗
```

`memory_query` 只允许基于以下证据回答：

- `memory_profile`
- mem0 memories
- 当前 thread 的可靠上下文

查不到时必须明说，不得猜测：

```text
我目前没有可靠记录你是谁。你可以告诉我你的名字或身份，我之后会按你的授权记住。
```

## Executor Router

执行器路由应消费 `IntentDecision`，而不是重新做全局意图判断。

```text
Executor Router:
  template_executor      fact_update / simple chitchat
  memory_executor        memory_query
  rag_executor           knowledge_query
  action_executor        client_action
  deepagents_executor    complex planning / multi-step / uncertain open task
```

deepagents / ReAct 是复杂任务执行策略，不是系统级兜底。它只能在已授权、已定界的任务内动态规划，不能绕过 Policy Gate 决定写记忆、执行高风险工具或伪造 RAG 来源。

## Agent 级兜底

系统级 fallback 不是“最后交给大模型试试看”。真正的 fallback 是分层降级与恢复机制。

| 失败层 | 条件 | 兜底策略 |
|--------|------|----------|
| intent | 低置信 | 问澄清问题，或走保守 executor |
| intent | 规则与模型冲突 | 禁止 fast path，记录 conflict，必要时澄清 |
| memory | 查不到用户记忆 | 明说没有可靠记录，邀请用户补充 |
| memory | 写入后台失败 | 不阻塞本轮，记录失败，进入补偿或告警 |
| RAG | 检索为空 | 明说知识库未找到来源，避免编造引用 |
| RAG | 召回弱 | 二查或澄清，不直接给确定性答案 |
| tool | 工具不可用或无权限 | 明说不可用，不假装执行 |
| tool | 高风险动作 | human-in-the-loop 审批 |
| LLM | timeout | 重试一次、降级模型或模板回复 |
| schema | 结构化输出非法 | repair 一次，仍失败则安全错误回复 |
| output guard | 输出违规 | retract / replace / refusal |
| checkpoint | 状态写入失败 | 不继续执行副作用动作，返回可恢复错误 |

全局铁律：

```text
不确定就降权。
缺证据就明说。
有副作用就审批。
失败必须记录。
```

## Human-in-the-loop

以下场景应支持 HITL 或显式用户确认：

- 高风险客户端工具动作。
- 未来服务端工具的写操作、删除操作、外部发送操作。
- 低置信但高影响的记忆写入。
- 安全策略不确定的请求。
- 用户纠错后需要修改长期记忆。

HITL 决策结果应结构化记录：

```text
approve
edit
reject
respond
```

## 反馈闭环

新增 `intent_feedback` 事件，用于把线上失败变成可回归样本。

```python
IntentFeedback(
    original_text="我是谁",
    predicted_route="fact_update",
    corrected_route="memory_query",
    failure_type="false_positive_fact_update",
    trace_id="...",
    thread_id="...",
    user_id="...",
    note="用户是在问记忆，不是在写事实",
)
```

反馈来源：

- 用户明确纠错。
- 人工 trace review。
- LangSmith evaluator 标记失败。
- path contract 失败。
- fallback manager 记录的低置信或冲突样本。

反馈去向：

- `agent/evals/intent_seed.json`
- LangSmith Dataset
- pytest 回归测试
- classifier few-shot examples
- deterministic rule conflict cases

## 评测要求

控制面变更必须建立专门评测集。

### Intent Eval

至少覆盖：

- 第一人称事实写入。
- 第一人称记忆查询。
- 企业知识库查询。
- 客户端工具动作。
- 模糊指代。
- 普通生成。
- 寒暄。
- 安全拒绝。

第一批必须包含以下反例：

```text
我是谁
我叫什么
我的名字是什么
你知道我是谁吗
我在哪里工作
我多大
我的生日是什么
我公司在哪
我喜欢什么
我是做什么的
```

### Path Eval

每条样本不仅验证最终回答，还要验证路径：

```text
expected.route
expected.executor
expected.rewrite_called
expected.rag_called
expected.supervisor_called
expected.llm_call_count_max
expected.fallback_allowed
```

### Memory Eval

验证：

- `memory_write` 是否只在高置信事实写入时触发。
- `memory_query` 是否不写入 mem0。
- 查不到记忆时是否诚实回答。
- 新旧记忆冲突是否有策略记录。

### Tool Eval

验证：

- 无权限工具不执行。
- 高风险工具需要审批。
- client_actions 不混入自然语言承诺。

## 可观测性

每轮 trace metadata 应至少包含：

```text
intent.speech_act
intent.domain
intent.operation
intent.route
intent.confidence
intent.risk
intent.reasons
intent.needs_clarification
policy.fast_path_allowed
policy.fast_path_denied_reason
executor.selected
fallback.triggered
fallback.layer
fallback.reason
feedback.recorded
```

path contract 应继续记录：

```text
rewrite.should_call / called
rag.should_call / called
supervisor.should_call / called
llm_call_count
path_contract
path_contract_reason
```

## 建议目录结构

```text
agent/src/
├── contracts/
│   └── intent.py          # IntentDecision, SpeechAct, IntentDomain, IntentOperation, RouteType, IntentRisk
├── intent/
│   ├── engine.py          # classify_intent()
│   ├── signals.py         # deterministic signal extraction
│   ├── rules.py           # high-confidence rules
│   ├── classifier.py      # small-model structured classifier
│   ├── policy.py          # fast path, HITL, fallback admission
│   ├── fallback.py        # fallback decisions
│   └── feedback.py        # feedback event helpers
├── graph/
│   └── nodes/
│       ├── intent_nodes.py
│       ├── routing_nodes.py
│       └── executor_nodes.py
└── memory/
    └── query.py           # memory_query executor support
```

## 迁移策略

### Phase 1: 契约和评测先行

- 新增 `contracts/intent.py`。
- 新增 intent eval seed。
- 将现有 `turn_type` 样本迁移为 `IntentDecision` 预期。
- 不改变运行路径。

### Phase 2: Intent Engine 影子运行

- 在现有 `turn_type` 分类旁边运行新 `classify_intent()`。
- trace 同时记录旧 `turn_type` 和新 `intent.route`。
- 发现分歧时记录 conflict，不改变线上行为。

### Phase 3: Policy Gate 接管 fast path

- `fact_update` fast path 改为由 Policy Gate 准入。
- `is_user_fact_statement()` 不再直接触发 fast path。
- 补齐第一人称疑问反例测试。

### Phase 4: memory_query 一等路径

- 新增 memory executor。
- 「我是谁」「我叫什么」「我公司在哪」走 memory read。
- 查不到时走诚实缺失回复。

### Phase 5: fallback manager 显式化

- 将低置信、冲突、RAG empty、tool unavailable、schema invalid 等统一记录。
- 补 trace metadata、LangSmith evaluator 和本地 path eval。

### Phase 6: feedback 闭环

- 用户纠错和人工 review 可写入 intent feedback。
- feedback 样本进入 eval seed。
- 改 intent 前必须跑控制面评测。

## 验收标准

- 「我是谁」不再可能进入 `fact_update`。
- 「我叫什么」「我的名字是什么」「我公司在哪」进入 `memory_query`。
- 「我叫张三」「我公司在天翔街188号」仍能进入高置信 `fact_update` fast path。
- `fact_update` fast path 需要 policy 准入，不再由事实正则直接决定。
- 低置信 intent 不触发 memory write、client action 或高风险工具。
- RAG 空结果不产生伪引用。
- 工具不可用时不承诺已执行。
- deepagents 只作为 executor，被 Policy Gate 约束。
- LangSmith trace 能看到完整 intent、policy、executor、fallback 字段。
- intent eval 覆盖第一批反例，并成为后续控制面改动的必跑测试。

## 风险与代价

| 风险 | 说明 | 缓解 |
|------|------|------|
| 架构变重 | 新增控制面会增加模块数量 | 先影子运行，不一次性替换全部路径 |
| 规则过度保守 | 部分事实写入不走 fast path | 接受漏判，后续用 eval 和反馈提高召回 |
| LLM classifier 成本 | 不确定场景可能多一次小模型 | 只在规则低置信或冲突时调用 |
| feedback 数据质量 | 用户纠错和人工标注可能不稳定 | 结构化 failure_type 和 review 流程 |
| 与旧 turn_type 兼容 | 现有路径依赖 `turn_type` | `turn_type = route`，渐进迁移 |

## 结论

这不是修复「我是谁」一个 case，而是重建 Agent 的控制面。

能力层负责做事，控制面负责决定能不能做、该由谁做、失败时怎么退、错误如何进入改进闭环。只有这层建立起来，mem0、RAG、client_actions 和 deepagents 才不会互相打补丁，系统也才能从“能跑”走向“可治理”。
