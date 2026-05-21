---
name: Agent Architecture Learning Notes
overview: 基于当前 Agent 架构和运行时优化 PRD 的学习笔记：指出设计短板、解释优化背后的工程原则。
isProject: false
---

# Agent 架构学习笔记

这份文档不是任务卡，也不是批评清单。它用于总结当前 Agent 设计暴露出的短板，以及下一阶段优化能带来的工程认知。

## 你当前设计里的优点

先确认基础判断是对的：

- 你把 Front、Back、Agent 分开，边界清楚。
- 你坚持 `user_id`、`role_id`、`tools[]` 每轮从 context 注入，而不是写进 checkpoint state，这个判断很重要。
- 你没有让浏览器直连 Agent，安全边界是对的。
- 你把外部工具定义成 `client_actions`，Agent 不执行、不等待、不 resume，第一期复杂度可控。
- 你愿意用 LangSmith trace 反推真实问题，而不是只看本地单测。

真正需要提高的是：如何从“能跑”升级到“可控、可扩展、低成本、好观测”。

## 主要短板

### 1. 太容易让 LLM 接管所有问题

现在很多输入都会进入 rewrite、router、Supervisor。真实 trace 说明了这一点：

- 「我出生于1997年」不该 rewrite，却被小模型改错。
- 「我公司在天翔街188号」不该 router LLM，却触发 timeout。
- 「我生活在哈尔滨」即使 rewrite/router 都很快，也多走了两次 LLM。

要学到的点：

LLM 不是默认执行器，而是最后手段。能用规则、状态机、模板解决的路径，应优先用确定性逻辑。

### 2. 缺少统一意图层

当前 rewrite、router、RAG、Supervisor 都在各自位置判断“这句话该不该处理”。这会造成规则分散：

- rewrite 补一套事实判断。
- router 再补一套事实判断。
- Supervisor 还可能继续回答事实写入。

要学到的点：

复杂 Agent 需要先判断 turn type，再让下游按类型执行。否则每个节点都会长出自己的小路由，最后变成补丁堆。

### 3. 把“正确结果”和“低成本路径”混在一起看

比如 `rag_router` 最终返回 `rag_skipped=true`，结果是对的；但它调用了一次小模型，路径是不对的。

要学到的点：

Agent 评估不只看最终回答，还要看路径是否合理：

- 有没有多余 LLM 调用？
- 有没有多余 RAG？
- 有没有不该进主模型的输入？
- fallback 是不是静默发生？

怎么落地：

给每类输入定义 **Path Contract（路径契约）**。它不是用户可见功能，而是工程验收标准。

| 输入 | 最终结果 | 路径契约 |
|------|----------|----------|
| 我出生于1997年 | 返回确认 | `fact_update`；0 次 LLM；0 次 RAG |
| 我生活在哈尔滨 | 返回确认或自然回应 | `fact_update`；不调用 rewrite/router/Supervisor |
| 你好 | 问候回复 | `chitchat`；不调用 RAG；最多模板/小模型 |
| 报销制度是什么 | 回答制度并引用来源 | `knowledge_query`；必须 RAG |
| 它需要什么材料 | 能消解“它” | `ambiguous`；允许 rewrite；按改写后意图决定 RAG |
| 打开 pageA | 返回 `client_actions` | `client_action`；不调用 RAG |

每轮 trace 都应该能回答：

1. 这轮 `turn_type` 是什么？
2. rewrite 是否应该调用，实际有没有调用？
3. router LLM 是否应该调用，实际有没有调用？
4. RAG 是否应该检索，实际有没有检索？
5. Supervisor/deepagents 是否应该调用，实际有没有调用？
6. 本轮 LLM 调用次数是多少？
7. 有没有 fallback？
8. 最终答案正确但路径是否失败？

落到代码上，就是在 trace metadata 或 state 里记录：

```text
turn_type=fact_update
fast_path=true
rewrite.should_call=false
rewrite.called=false
rag_router.should_call=false
rag_router.called=false
rag.should_call=false
rag.called=false
supervisor.should_call=false
supervisor.called=false
llm_call_count=0
path_contract=pass
```

如果实际路径不符合预期：

```text
path_contract=fail
path_contract_reason=unexpected_rewrite_llm
```

测试也要这样写：不要只断言“答案包含哈尔滨”，还要断言“没有调用 rewrite/router/Supervisor LLM”。

这就是从“结果正确”升级到“系统正确”。Agent 的正确性不是只有用户看到的文本，还包括它为了生成文本走过的路径。

### 4. 对后台失败的产品语义还不够明确

`fact_update` 如果直接返回“已记住”，但 mem0 后台写失败，语义上会有风险。

要学到的点：

异步系统里要区分：

- 接收成功：Agent 收到这条事实。
- 持久化成功：mem0 确实写入。
- 可恢复失败：后台可重试。

第一期可以给用户模板确认，但系统内部必须有失败日志、trace、指标和补偿方案。

### 5. 对“流式”的理解容易停在接口形态

当前 SSE 是完整 graph 结束后切块，这只是 SSE 传输，不是真流式体验。

要学到的点：

真流式关注的是 first token latency。流式不是“把最终答案分段发”，而是模型边生成、服务边转发、前端边展示。

同时，流式和护栏天然冲突：

- 整段护栏安全，但慢。
- 乐观流式快，但可能需要撤回。

这就是 optimistic streaming、streaming moderation、post-hoc moderation 要解决的问题。

### 6. 对 deepagents 的定位需要更精确

你希望 deepagents 能让 Agent 未来服务 Web 应用，这是对的。但不是所有输入都应该走 deepagents。

要学到的点：

deepagents 应该是复杂任务执行器，不是所有回复的默认入口。

更合理的分层：

- 模板：事实写入、固定确认。
- 小模型：寒暄、轻量自然回复、简单分类。
- 普通 ChatOpenAI：RAG 问答、一般聊天。
- deepagents：多步规划、工具编排、长任务、跨页面工作流、服务端工具。

### 7. 记忆需要从“文本列表”升级到“可治理资产”

mem0 自由文本很方便，但多了以后会遇到：

- 重复事实。
- 旧事实和新事实冲突。
- 不知道哪些事实该进 system。
- 隐私字段难删除。
- 上下文膨胀。

要学到的点：

长期记忆不是“越多越好”，而是要可分类、可更新、可删除、可预算。类别化 schema 是走向稳定产品的必要步骤。

### 8. RAG 不能只靠“能搜到”

当前 RAG 管线能跑，但缺少评测集，质量判断主要靠手感。

要学到的点：

RAG 是检索系统，不只是 LLM prompt。需要评估：

- 召回是否正确。
- role_id 是否越权。
- 引用是否准确。
- rerank 是否真的提升。
- 改动前后指标是否变好。

LangSmith Dataset 的价值在这里：把问题、期望答案、期望引用和运行结果放到同一个可比较体系里。

## 这轮优化能学到什么

### 1. 先做路由，再做智能

不要一上来就问“哪个模型更好”。先问：

- 这轮需不需要模型？
- 需不需要 RAG？
- 需不需要 deepagents？
- 能不能模板返回？

模型选择是第二层问题，路径选择是第一层问题。

### 2. Agent 是工作流，不是单个大 prompt

一个可靠 Agent 应该像后端系统一样拆职责：

- intent / turn type
- memory read/write
- rewrite
- retrieval
- answer
- tools
- guardrails
- observability

每层都要有输入、输出、fallback 和可观测字段。

### 3. Trace 是事实来源

这次几个判断都来自 trace：

- rewrite 改错数字。
- router timeout。
- 小模型虽快但不该调用。
- Supervisor token usage 异常大。

以后做 Agent，不要只问“代码看起来对不对”，要问“trace 证明它按预期走了吗”。

### 4. 成本控制要前置设计

成本不是上线后才优化的问题。Agent 每个节点都可能调用模型：

- rewrite
- router
- rerank
- mem0 infer
- summary
- supervisor
- subagent

如果不做 turn type 和预算，成本会从多个小口子漏出去。

### 5. fallback 不是随便吞错

fallback 有两种：

- 产品 fallback：失败后用户仍有合理体验。
- 工程 fallback：失败原因可追踪、可重试、可报警。

只吞异常返回默认值，会让系统“看似可用，实际不可控”。

### 6. 文档要从“架构说明”进化到“决策记录”

当前架构 PRD 说明系统怎么设计；优化 PRD 应该说明为什么要改、改到什么程度、什么不改、如何验收。

这类文档未来给 AI agent 看很重要，因为它能减少 AI 自作主张。

## 建议你后续重点练的能力

1. **路径意识**：每轮用户输入到底走了哪些节点，哪些节点本可跳过。
2. **成本意识**：每次 LLM 调用是否必要，输入 token 是否可控。
3. **状态意识**：哪些信息属于 checkpoint，哪些属于 request context，哪些只是一轮临时值。
4. **评测意识**：用 trace 和 dataset 判断改动，而不是只靠主观体验。
5. **产品语义意识**：一句“已记住”背后到底代表接收、写入中、写入成功，还是可恢复失败。
6. **分层执行意识**：模板、小模型、普通模型、deepagents 各自该做什么。

## 一句话总结

你现在的 Agent 已经从“搭骨架”进入“运行时治理”阶段。下一步真正要学的是：少让大模型做不必要的事，把每一次模型调用都变成有理由、有边界、可回放、可评估的工程决策。
