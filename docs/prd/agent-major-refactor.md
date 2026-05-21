---

## name: Agent Major Refactor
overview: 面向人类与 AI 可维护性的 Agent 大重构 PRD 草案：契约优先、薄图编排、显式状态生命周期、可插拔 RAG、统一 LLM 网关与测试护栏。
isProject: false

# Agent 大重构（PRD 草案）

## 文档定位

本文是下一阶段“大重构”讨论稿，不替代当前 [README.md](../../README.md) 的运行契约，也不表示现有实现需要立即重写。

当前 01-40 任务已经完成，系统具备 Front -> Back -> Agent、checkpoint、mem0、RAG、Supervisor、client_actions、SSE、LangSmith tracing 与评测种子。大重构的目标不是补齐功能，而是让代码结构长期更适合人类维护，也更适合 AI agent 在局部上下文中安全修改。

## 背景

当前实现能跑通目标链路，但代码可维护性上存在几个高成本点：

- 图节点逻辑集中在少数大文件中，尤其是 `graph/nodes.py`、`rag/retriever.py`、`memory/assembly.py`、`observability/tracing.py`。
- 单轮中间状态依赖 `EphemeralValue` 与 `_EPHEMERAL_CARRY_KEYS` 手工同步，新增字段时容易漏掉 producer / consumer / carry 关系。
- `turn_type`、`executor`、`path_metrics`、reason code、trace metadata 等运行时契约大量使用 string / dict，类型系统无法保护。
- Context 组装和实际模型调用之间存在重复构建路径，观测值与实际调用值未来可能分叉。
- RAG 检索把 Qdrant、dense、BM25、text search、rerank、mock、metadata 混在一个文件里，不利于替换和调参。
- LLM 调用分散在 rewrite、router、chitchat、supervisor、mem0、rerank 等模块中，模型策略、timeout、trace 与降级逻辑难以统一。
- 现有测试覆盖较多，但目录和验证入口还不够表达“契约层 / 纯逻辑层 / pipeline 层 / eval 层”的意图。

## 目标

1. 让目录结构表达职责边界，读目录即可大致知道修改范围。
2. 让核心运行契约类型化，减少 stringly-typed 和 ad hoc dict。
3. 让 LangGraph 只负责流程连线和 adapter，业务逻辑可脱离 LangGraph 单测。
4. 显式声明 state 字段生命周期：跨轮持久、单轮传递、节点内部私有。
5. 建立可读的 pipeline spec，使人和 AI 能先读流程，再读实现。
6. 将 context 组装变成单一事实来源，避免观测和实际模型输入分叉。
7. 将 RAG、LLM、observability 做成可替换基础设施和领域服务。
8. 建立分层测试护栏，在大规模迁移中锁住现有行为。

## 非目标

- 不改变 Front -> Back -> Agent 三层边界。
- 不让浏览器直连 Agent。
- 不把客户端外部工具改成 Agent 服务端执行。
- 不在第一步引入新的产品功能。
- 不以“抽象更多”为目的；抽象只服务于明确的契约、替换点和测试边界。
- 不一次性删除 deepagents；是否保留、分层或替换由后续 executor 设计决定。

## 设计原则

### 契约优先

核心数据结构应先有清晰契约，再有实现。所有跨模块传递的数据都应有稳定类型和文档注释。

优先类型化的契约：


| 契约                       | 说明                                                                                                      |
| ------------------------ | ------------------------------------------------------------------------------------------------------- |
| `TurnType`               | `fact_update`、`chitchat`、`knowledge_query`、`client_action`、`ambiguous`、`general_chat`                   |
| `ExecutorType`           | `template_executor`、`small_chat_executor`、`rag_answer_executor`、`action_executor`、`deepagents_executor` |
| `PathComponent`          | `rewrite`、`rag_router`、`rag`、`rag_subagent`、`supervisor`、`post_turn`                                    |
| `PathMetrics`            | 每个阶段 should/called/pass/reason/error                                                                    |
| `ContextBundle`          | `system_prompt`、`model_messages`、`budget`、`sources`                                                     |
| `ContextBudget`          | system/messages/RAG/memory/tools 的预算结果                                                                  |
| `RagChunk` / `RagResult` | 检索结果、通道来源、分数、引用                                                                                         |
| `SseEvent`               | `token`、`done`、`client_actions`、`retract`、`replace`、`error`                                             |
| `GraphStatePatch`        | 节点返回的 typed state 更新                                                                                    |


### 薄图编排

LangGraph 节点只做三件事：

1. 从 `AgentState` 和 `RuntimeContext` 读取输入。
2. 调用 application/domain service。
3. 返回 `GraphStatePatch`。

业务逻辑不直接依赖 LangGraph，使单元测试可以直接测 domain/application service。

### 显式状态生命周期

每个 state 字段必须声明生命周期：


| 生命周期         | 含义                                | 示例                                        |
| ------------ | --------------------------------- | ----------------------------------------- |
| `Persistent` | 跨轮 checkpoint 持久化                 | `messages`                                |
| `TurnLocal`  | 单轮内多个节点共享，下轮清空                    | `turn_type`、`rag_chunks`、`context_bundle` |
| `Private`    | 只在某个 service 内部使用，不进入 graph state | prompt 临时文本、raw provider response         |


`EphemeralValue` 仍可作为 LangGraph 实现细节，但不能再依赖手工 `_EPHEMERAL_CARRY_KEYS` 作为事实来源。字段 producer、consumer、生命周期应由集中声明生成或校验。

### 单一事实来源

同一份信息只应有一个权威来源：

- Context 模型输入来自 `ContextBundle`。
- 路径观测来自 `PathMetrics`。
- 请求身份来自 `RuntimeContext`，不进入 checkpoint。
- client action 输出来自 typed `ClientActionEnvelope`，不从自然语言中多处重复解析。

## 目标目录结构

建议目标结构：

```text
agent/src/
├── contracts/
│   ├── runtime.py          # Request/Runtime context, identity, tool context
│   ├── state.py            # state field definitions and lifecycle
│   ├── pipeline.py         # stage spec, producer/consumer declarations
│   ├── routing.py          # TurnType, route decisions
│   ├── execution.py        # ExecutorType, ExecutorDecision
│   ├── context.py          # ContextBundle, ContextBudget
│   ├── rag.py              # RagChunk, RagResult, retrieval metadata
│   ├── events.py           # domain events and observability events
│   └── sse.py              # typed SSE events
├── application/
│   ├── chat_turn.py        # one turn orchestration independent of FastAPI
│   ├── history_query.py
│   └── kb_ingest.py
├── graph/
│   ├── build.py            # graph wiring only
│   ├── adapters.py         # AgentState <-> contracts conversion
│   └── nodes/
│       ├── guardrail_nodes.py
│       ├── memory_nodes.py
│       ├── routing_nodes.py
│       ├── rag_nodes.py
│       ├── context_nodes.py
│       ├── executor_nodes.py
│       └── post_turn_nodes.py
├── domain/
│   ├── guardrails/
│   ├── memory/
│   ├── routing/
│   ├── rag/
│   ├── context/
│   └── execution/
├── infrastructure/
│   ├── llm/
│   ├── qdrant/
│   ├── postgres/
│   ├── mem0/
│   └── langsmith/
└── gateway/
    ├── app.py
    ├── chat.py
    ├── history.py
    └── ingest.py
```

目录含义：


| 层                | 职责                                           |
| ---------------- | -------------------------------------------- |
| `contracts`      | 跨模块类型、生命周期、稳定枚举和事件                           |
| `application`    | 用例编排，不依赖 FastAPI，不直接调用具体基础设施                 |
| `graph`          | LangGraph wiring 和 adapter                   |
| `domain`         | 纯业务规则和可组合服务                                  |
| `infrastructure` | provider / DB / LangSmith / mem0 / Qdrant 适配 |
| `gateway`        | HTTP、SSE、schema、错误码                          |


## Pipeline Spec

新增显式 pipeline spec，用来表达阶段顺序、条件、输入输出和观测。

示例：

```python
CHAT_TURN_PIPELINE = [
    Stage(
        name="inbound_guard",
        produces=["inbound_blocked", "inbound_block_message"],
        lifecycle="TurnLocal",
    ),
    Stage(
        name="load_memory",
        requires=["messages", "runtime_context"],
        produces=["mem0_memories", "rolling_summary"],
    ),
    Stage(
        name="classify_turn",
        requires=["messages", "tools"],
        produces=["turn_type", "turn_type_reason", "path_metrics"],
    ),
    Stage(name="rewrite", when="needs_rewrite"),
    Stage(name="rag_route", when="needs_rag_decision"),
    Stage(name="retrieve", when="needs_rag"),
    Stage(name="assemble_context"),
    Stage(name="execute"),
    Stage(name="outbound_guard", when="text_output"),
    Stage(name="post_turn_jobs"),
]
```

Pipeline spec 的用途：

- 生成或校验 `AgentState` TurnLocal 字段。
- 校验每个字段至少有 producer，必要字段有 consumer。
- 生成 `docs/maps/chat-turn-pipeline.md`。
- 驱动 path contract 测试。
- 给 AI 一个短而权威的流程入口。

## ContextBundle

Context 组装应只发生一次，产出 `ContextBundle`：

```python
ContextBundle(
    system_prompt=...,
    model_messages=...,
    budget=ContextBudget(...),
    sources=ContextSources(
        memory_profile=...,
        mem0_free_text=...,
        rolling_summary=...,
        rag_chunks=...,
        tools=...,
    ),
)
```

要求：

- `executor` 只消费 `ContextBundle`，不重新构建 system/messages。
- LangSmith metadata 来自同一个 `ContextBudget`。
- 测试可直接断言最终进入模型的 `system_prompt` 和 `model_messages`。
- `current_human`、`original_human` 的处理由 bundle builder 统一负责。

## RAG 重构

建议拆分当前 RAG：

```text
domain/rag/
├── query_plan.py       # rewrite 后 query / route decision 转 retrieval plan
├── merge.py            # dense/sparse/text/BM25 merge strategy
├── formatting.py       # prompt citation formatting
└── service.py          # retrieve orchestration

infrastructure/qdrant/
├── kb_store.py         # role scoped search/scroll/upsert/delete
├── dense_search.py
└── payload.py

domain/rag/lexical/
├── tokenizer.py
└── bm25.py

infrastructure/llm/
└── rerank_client.py
```

RAG service 输出 `RagResult`：

```python
RagResult(
    query=...,
    chunks=[...],
    dense_hits=...,
    lexical_hits=...,
    rerank_applied=True,
    fallback_used=False,
    errors=[],
)
```

验收：

- dense embedding 失败时，BM25 fallback 路径仍可独立测试。
- role_id 权限过滤在 store adapter 层和 service 层都有测试。
- rerank 可替换，不影响检索编排。
- RAG 格式化不依赖 Qdrant payload 细节。

## LLM Gateway

新增统一 LLM 网关，按用途声明调用策略：


| 用途            | 示例                   |
| ------------- | -------------------- |
| `MAIN_ANSWER` | 普通主回复或 deepagents 模型 |
| `RAG_ANSWER`  | 简单知识库问答              |
| `REWRITE`     | 指代消解                 |
| `ROUTER`      | 模糊 turn 的 RAG 分类     |
| `CHITCHAT`    | 轻量寒暄                 |
| `MEM0_WRITE`  | mem0 infer 写入        |
| `RERANK`      | rerank endpoint      |
| `EMBEDDING`   | embedding            |


统一管理：

- 模型选择。
- timeout。
- max tokens。
- temperature。
- retry 策略。
- streaming。
- trace metadata。
- provider 错误归一化。
- fallback 行为。

目标不是隐藏所有 provider 差异，而是让业务代码不再散落 `ChatOpenAI(...)`、`OpenAIEmbeddings(...)`、`urllib /rerank` 等调用细节。

## Observability 事件化

业务代码不应到处直接调用 `attach_run_metadata()`。建议改为事件：

```python
emit(Event.TurnClassified(...))
emit(Event.RewriteSkipped(...))
emit(Event.RagRetrieved(...))
emit(Event.ExecutorChosen(...))
emit(Event.ContextBudgetComputed(...))
emit(Event.PostTurnScheduled(...))
```

由 `infrastructure/langsmith` adapter 订阅事件并转换为 metadata / span。

好处：

- 业务逻辑和 LangSmith 解耦。
- metadata key 有集中定义。
- 后续可以同时输出结构化日志、metrics、LangSmith。
- 测试可断言事件，不必 mock LangSmith run tree。

## 测试策略

重构前先补 characterization tests，锁住当前行为。之后按四层组织测试：

```text
agent/tests/
├── contract_tests/
│   ├── test_state_lifecycle.py
│   ├── test_pipeline_spec.py
│   ├── test_env_contract.py
│   ├── test_sse_events.py
│   └── test_client_actions_contract.py
├── domain_tests/
│   ├── test_turn_routing.py
│   ├── test_context_bundle.py
│   ├── test_rag_merge.py
│   ├── test_bm25.py
│   └── test_memory_profile.py
├── pipeline_tests/
│   ├── test_fact_update_path.py
│   ├── test_chitchat_path.py
│   ├── test_knowledge_query_path.py
│   ├── test_client_action_path.py
│   └── test_ambiguous_path.py
└── eval_tests/
    ├── test_seed_schema.py
    └── test_rag_quality_smoke.py
```

测试目标：

- Contract tests 保证字段、schema、env、SSE、client_actions 不漂移。
- Domain tests 保证纯逻辑可独立理解和运行。
- Pipeline tests 保证每类 turn 的路径、LLM 调用次数、RAG 调用、executor 选择符合预期。
- Eval tests 保证质量回归可被发现。

## 迁移策略

### Phase 0：行为冻结

目标：不改结构，先补护栏。

- 修正测试入口和 Makefile 目标。
- 增加 state lifecycle 检查测试，覆盖 `AgentState` 与 `_EPHEMERAL_CARRY_KEYS`。
- 增加 pipeline path characterization tests。
- 增加核心 SSE event contract tests。

退出标准：

- 当前行为有足够测试描述。
- 大重构开始后能快速发现路径漂移。

### Phase 1：契约层落地

目标：新增 `contracts/`，先并行存在，不大规模改调用点。

- 定义 `TurnType`、`ExecutorType`、`PathMetrics`、`ContextBudget`、`ContextBundle`、`SseEvent`。
- 新老结构之间加 adapter。
- 把 reason code 常量集中管理。

退出标准：

- 新契约可被测试直接导入。
- 旧实现仍可通过 adapter 使用。

### Phase 2：ContextBundle 单一来源

目标：消除 context 重复构建。

- `context_assembly` 产出 `ContextBundle`。
- executor 只消费 bundle。
- tracing metadata 来自 bundle.budget。

退出标准：

- 模型实际输入和 trace budget 来自同一对象。
- 相关旧函数标记为兼容层或删除。

### Phase 3：拆分 Graph Nodes

目标：把 `graph/nodes.py` 拆成按阶段组织的小文件。

- 先不改行为，只移动代码和测试。
- 每个 node 文件只负责 adapter。
- 复杂逻辑迁入 domain/application service。

退出标准：

- 单个 node 文件能在 200 行以内。
- 每个 graph node 的输入输出可以从类型看出来。

### Phase 4：RAG 模块化

目标：拆出 Qdrant store、lexical/BM25、rerank、service 编排。

- 保留现有外部 API。
- 将 Qdrant payload 解析收敛到 store adapter。
- 将 BM25 tokenizer 和 scorer 纯函数化。

退出标准：

- dense、lexical、rerank、merge 可分别单测。
- Qdrant mock 和 live path 边界清晰。

### Phase 5：LLM Gateway

目标：统一模型调用策略。

- 引入 `ModelUseCase`。
- rewrite/router/chitchat/rag_answer/supervisor/mem0/rerank/embedding 逐步迁移。
- 统一 timeout、max tokens、retry、trace。

退出标准：

- 业务层不直接构造 provider client。
- 成本和延迟配置按 use case 可观测。

### Phase 6：Observability 事件化

目标：业务逻辑不直接写 LangSmith metadata。

- 引入 domain events。
- LangSmith adapter 订阅事件。
- 保留旧 metadata key 的兼容输出，避免 trace 看板断裂。

退出标准：

- 业务测试断言事件。
- LangSmith 输出仍覆盖原有关键 metadata。

### Phase 7：文档地图

目标：为人和 AI 提供短入口。

新增：

```text
docs/maps/
├── chat-turn-pipeline.md
├── state-fields.md
├── llm-calls.md
├── rag-flow.md
├── client-actions.md
└── failure-modes.md
```

退出标准：

- 每份文档都能在 5 分钟内回答一个维护问题。
- 文档指向代码位置和测试位置。

## 验收标准

### 可读性

- 新人或 AI 从 `docs/maps/chat-turn-pipeline.md` 能定位每个阶段的实现文件。
- `AgentState` 每个字段都有生命周期、producer、consumer。
- 修改某个 executor 不需要阅读整个 graph。
- 修改 RAG rerank 不需要阅读 ingest 和 gateway。

### 稳定性

- 原有单元测试通过。
- 新增 contract/pipeline tests 通过。
- 典型 turn path 不漂移：
  - `fact_update` 不调用 rewrite/router/RAG/Supervisor。
  - `chitchat` 不调用 RAG/deepagents。
  - `knowledge_query` 能触发 RAG。
  - 简单 `client_action` 能结构化输出。
  - `ambiguous` 能按需要 rewrite。

### 可观测性

- trace/log 中仍能看到 turn type、executor、RAG hit、context budget、LLM use case、post_turn 状态。
- metadata key 迁移有兼容策略。

### AI 友好

- 每个模块有清晰输入输出类型。
- 业务逻辑可脱离框架单测。
- 流程和字段关系可由 pipeline spec / state lifecycle 直接读取。
- 少量局部上下文即可修改一个阶段。

## 风险


| 风险              | 说明                  | 缓解                                |
| --------------- | ------------------- | --------------------------------- |
| 大重构引入行为漂移       | 路径和降级策略可能被误改        | Phase 0 先补 characterization tests |
| 类型层过度设计         | 抽象多但收益小             | 只类型化跨模块契约，不类型化局部临时变量              |
| 迁移周期长           | 新旧结构并存会短期增加复杂度      | 每个 phase 有退出标准，避免长期半迁移            |
| Trace 看板断裂      | metadata key 改名影响观察 | 事件化时保留旧 key 兼容输出                  |
| AI 误把 PRD 当当前契约 | 草案与 README 混淆       | 文档顶部明确“不替代 README”                |


## 待讨论问题

1. `contracts/` 使用 Pydantic 还是 dataclass + Enum？边界 API 更适合 Pydantic，纯内部对象可能 dataclass 更轻。
2. Pipeline spec 是只做文档/测试输入，还是直接驱动 graph build？
3. `GraphStatePatch` 是否值得做成统一对象，还是保持 dict 但增加 typed helper？
4. 是否保留 deepagents 作为复杂任务 executor，还是后续替换成普通 ChatOpenAI + 自研 planner？
5. LLM Gateway 第一阶段先覆盖 chat/rewrite/router，还是连 embedding/rerank 一起纳入？
6. Observability event bus 用简单同步 collector，还是引入更完整的事件发布机制？
7. 文档地图是否应由 pipeline spec 自动生成，还是先人工维护？

## 建议决策顺序

1. 先确认是否接受“契约优先 + 薄图编排 + domain/application/infrastructure 分层”的方向。
2. 再决定 Phase 0 是否先做测试入口和 characterization tests。
3. 然后讨论 `contracts/` 的类型技术选型。
4. 最后拆任务卡，避免一次性大 PR。

