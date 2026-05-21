---
name: Agent Runtime Optimization
overview: 下一阶段 Agent 运行时优化 PRD 草案：减少无效 LLM 调用、真流式、上下文预算、mem0 成本控制、RAG 质量与可观测性。
isProject: false
---

# Agent 运行时优化

## 背景

第一期已经跑通 Front -> Back -> Agent，具备 checkpoint 历史、mem0 长期记忆、RAG、Supervisor、client_actions 和 LangSmith tracing。

近期真实 trace 暴露出几个问题：

- 事实陈述类输入（如「我出生于1997年」「我公司在天翔街188号」「我生活在哈尔滨」）本应写记忆或直接确认，却可能触发 rewrite/router 小模型，甚至继续进入 Supervisor 大模型。
- 小任务模型虽然降到约 1 秒，但高频无效调用会累积关键路径延迟。
- Supervisor 使用 deepagents + 主模型，trace 中出现高 token usage，成本和延迟风险较大。
- 当前 SSE 是 graph 完成后切块，不是首 token 真流式。
- rewrite/router 规则持续补丁化，缺少统一的 turn type 决策层。

本 PRD 只讨论下一阶段目标和验收，不直接替代现有架构 PRD。

## 目标

1. 降低普通对话关键路径延迟，尤其是事实陈述、寒暄、纯 client_action 场景。
2. 减少不必要的 rewrite/router/Supervisor LLM 调用。
3. 建立统一 turn type，让后续路由、记忆、RAG、工具动作按类型决策。
4. 将 SSE 改为真正可感知的流式输出。
5. 控制上下文、mem0、RAG 和 Supervisor 的 token 成本。
6. 提升 RAG 召回质量和失败可观测性。

## 非目标

- 不改变 Front -> Back -> Agent 的边界。
- 不让浏览器直连 Agent。
- 不把外部 client_actions 改成 Agent 服务端工具。
- 不一次性重写所有图节点；优先做关键路径优化。

## 核心方案

### 1. Turn Type 路由层

在 `load_memory` 后、`rewrite` 前增加或内联一个确定性优先的 `turn_type` 决策。

建议类型：

| turn_type | 示例 | 后续行为 |
|-----------|------|----------|
| `fact_update` | 我生活在哈尔滨 / 我公司在天翔街188号 | 跳过 rewrite、RAG、Supervisor；写入 mem0 后返回简短确认 |
| `chitchat` | 你好 / 谢谢 | 跳过 rewrite、RAG；可用轻量模板或小模型回复 |
| `knowledge_query` | 报销制度是什么 | 可跳过 rewrite 或仅必要时 rewrite；走 RAG |
| `client_action` | 打开 pageA | 跳过 RAG；直接让 Supervisor 或结构化生成器产出 client_actions |
| `ambiguous` | 它怎么办 / 继续说 | 走 rewrite，再决定 RAG |
| `general_chat` | 非知识库闲聊/开放聊天 | 跳过 RAG；可进 Supervisor |

验收：

- `fact_update` 不产生 rewrite/router/Supervisor ChatOpenAI span。
- `knowledge_query` 仍能触发 RAG。
- `ambiguous` 仍能利用 rewrite 消解指代。

### 2. 事实写入快速路径

对 `fact_update` 增加快速路径：

1. 当前 human 进入 checkpoint。
2. 直接返回确认文案，例如「已记住。」或「好的，我记住了。」
3. post_turn 异步执行 mem0 `add(infer=True)`。

注意：

- 不在同步链路等待 mem0 写入完成。
- 确认文案不应复述敏感信息过多。
- 如果 inbound guard 阻断，不能写 mem0。
- 模板确认只代表 Agent 已接收本轮事实，不承诺 mem0 已持久化成功。
- mem0 写入失败时不撤回用户已看到的确认，但必须记录失败状态：LangSmith metadata、结构化日志、失败计数；后续可做重试队列或后台补偿任务。
- 对关键事实可选“待确认/待落库”状态，但第一期不把这个状态暴露给用户，避免每轮事实写入都阻塞。

验收：

- 「我出生于1997年」端到端不调用任何 LLM 也能返回。
- mem0 后台写入失败只影响记忆，不影响本轮确认。
- mem0 写入失败能通过 trace/log/metrics 定位到 `thread_id`、`user_id` 和失败原因。

### 3. rewrite/router 策略收敛

rewrite 只解决「指代/省略导致检索不可用」问题，不做事实润色。

规则：

- 默认不 rewrite。
- 只有检测到指代、承接、或历史依赖时才 rewrite。
- rewrite 输出必须通过事实保护：数字、日期、姓名、地点、职业等原文事实不得被修改。

router 只处理是否需要企业知识库：

- `fact_update`、`chitchat`、`client_action` 直接 skip RAG。
- `knowledge_query` 直接 retrieve。
- 只有 `ambiguous/general_chat` 且规则无法确定时，才调用 router 小模型。

验收：

- LangSmith 中 rewrite/router 小模型调用率显著下降。
- router timeout 不再出现在事实写入场景。

### 4. 真流式输出

当前 SSE 是 graph 完成后切块，用户首 token 仍等待完整推理结束。

目标：

- Gateway 使用 LangGraph streaming / model streaming，将 Supervisor token 实时转发。
- 仍保留 client_actions 的 JSON 响应模式。
- 出站护栏采用乐观流式策略：先展示流式内容，按句子级/固定窗口做增量检查；若后续发现违规，发送撤回/替换事件。

术语：

- **Optimistic streaming**：先把模型输出展示给用户，再用异步或滞后的安全检查纠偏。
- **Streaming moderation / incremental moderation**：对流式 token 按句子或窗口持续做安全检测。
- **Post-hoc moderation**：内容已经生成或展示后再做检查，必要时撤回或替换。
- **Output retraction**：前端收到撤回事件后隐藏、替换或标记已展示内容。

可选分阶段：

1. 句子级缓冲：模型输出先进入 server buffer，遇到句末或窗口上限后检查并发送。
2. 乐观前端展示：低风险内容即时展示；如果后续窗口检查失败，发送 `retract` / `replace` SSE 事件。
3. 高风险模式降级：对敏感角色、敏感工具、敏感问题可回到整段出站护栏。

验收：

- 普通文本回复首 token 时间接近 Supervisor 首 token，而不是完整 graph 结束时间。
- client_actions 仍为结构化 JSON，不混入 SSE 文本。
- 前端能处理 `token`、`done`、`retract`、`replace` 事件。

### 5. Supervisor 简化与模型分层

当前 deepagents 对本项目外部工具链路价值还没有完全发挥出来，因为 client_actions 是 prompt 约束，不是 LangChain tool 执行。但项目长期目标是服务 Web 应用，未来会有更复杂的多步任务、跨页面操作、文档分析、服务端工具与子任务委派，deepagents 仍有保留价值。

候选方案：

| 方案 | 优点 | 风险 |
|------|------|------|
| 保留 deepagents | 少改动，已有能力保留 | token/latency 继续高 |
| 普通 ChatOpenAI Supervisor | 可控、轻量、易流式 | 需要重做少量 prompt 和输出解析 |
| 双 Supervisor | 简单问答走轻量模型，复杂任务走 deepagents | 路由复杂度增加 |

建议做分层执行器，而不是去掉 deepagents：

| executor | 适用场景 | 模型/机制 |
|----------|----------|-----------|
| `template_executor` | `fact_update`、固定确认、低风险 chitchat | 模板，无 LLM |
| `small_chat_executor` | 普通寒暄、轻量改写、简单解释 | 小模型 |
| `rag_answer_executor` | 明确知识库问答，RAG chunks 已足够 | 普通 ChatOpenAI，可真流式 |
| `action_executor` | 简单 client_actions，如打开页面 | 结构化生成器或小模型 |
| `deepagents_executor` | 多步规划、复杂业务操作、需要内置/服务端工具、长文档分析、跨页面工作流 | deepagents + 强模型 |

deepagents 触发条件建议：

- 用户明确要求“帮我完成一件事”，且任务超过单轮问答。
- 需要多步计划、文件/文档处理、服务端工具、子 Agent 或长上下文综合。
- RAG 初答置信不足且需要进一步分解问题。
- client_actions 不是单一跳转，而是多动作流程。

不触发 deepagents 的场景：

- `fact_update`。
- 纯寒暄或感谢。
- 明确的单跳 client_action。
- RAG chunks 已足够支撑的简单知识库问答。

验收：

- 简单输入不再触发 deepagents middleware 链。
- trace 中 Supervisor token usage 明显下降。
- deepagents 仍在复杂任务中可被明确触发，并能在 trace 中看到触发原因。

### 6. mem0 成本与质量控制

现状 mem0 读默认 50 条，写入 infer 使用主模型配置，可能增加成本和背景队列压力。

优化：

- mem0 写入使用专用小模型配置，不默认使用 `OPENAI_MODEL_NAME`。
- mem0 读侧按当前 turn type/query 做筛选，限制注入 system 的事实数量。
- 引入类别化 schema，对事实按类别去重，例如身份、职业、城市、公司地址只保留最新或置信最高。
- 对敏感字段增加删除/更新策略。

类别化 schema 建议：

| 类别 | 示例 key | 示例值 |
|------|----------|--------|
| 个人身份 | `profile.name` | 刘日兴 |
| 个人属性 | `profile.birth_year`、`profile.city` | 1997、哈尔滨 |
| 职业 | `profile.job` | 前端程序员 |
| 公司信息 | `company.address` | 天翔街188号 |
| 偏好 | `preference.answer_style` | 简洁回答 |

利弊：

| 方案 | 优点 | 缺点 |
|------|------|------|
| 自由文本事实 | 实现简单；兼容 mem0 原生输出；适合探索期 | 去重难；同类事实会重复；检索和更新不稳定 |
| 类别化 schema | 易去重、更新、删除；更适合权限和隐私控制；上下文注入可按类别选择 | 需要抽取/归一化逻辑；schema 设计不当会限制表达；需要迁移旧事实 |

建议：

- 短期保留 mem0 自由文本作为原始事实来源。
- 新增一层应用侧 `memory_profile` 归一化视图，把高频稳定字段类别化。
- 注入 system 时优先使用类别化事实，剩余自由文本只取少量相关项。

验收：

- system prompt 中 mem0 facts 默认不超过配置上限。
- mem0 写入不使用主回复模型。
- 同一事实反复输入不会让 system prompt 膨胀。

### 7. 上下文预算

目标是所有进入主模型的上下文有明确预算。

建议预算项：

| 内容 | 控制 |
|------|------|
| mem0 facts | top N + 字符上限 + 去重 |
| rolling summary | 字符上限 |
| recent messages | M 上限，按 token 估算裁剪 |
| RAG chunks | chunk 数 + 单 chunk 字符上限 |
| tools 描述 | tool 数 + schema 压缩 |

验收：

- LangSmith metadata 记录 system_prompt_len、message_count、mem0_count、rag_chunk_count。
- 超预算时有明确裁剪顺序，不靠模型窗口硬截断。

### 8. RAG 质量提升

当前 RAG 可用但偏基础。

优化方向：

- 真 sparse query 向量或 BM25 服务，不只依赖 Qdrant payload text match。
- query expansion 只在 `knowledge_query` 且召回弱时触发。
- 增加 role_id/doc 权限测试集，防越权召回。
- 引入 LangSmith Dataset 作为主评测集，记录问题、期望引用、期望答案要点和角色权限。
- 本地保留一份轻量 JSON/Markdown seed，用于版本管理和快速 smoke test；需要时同步到 LangSmith Dataset。

验收：

- 有最小评测集覆盖 10-20 个企业知识库问题。
- 每次 RAG 改动能跑评测并比较指标。
- LangSmith Dataset 中能按版本查看 RAG 改动前后的召回和答案质量。

### 9. 错误与可观测性

当前很多失败会静默 fallback。

优化：

- 对 fallback 建立统一 reason code。
- LangSmith metadata 增加 `turn_type`、`fast_path`、`llm_call_count`。
- 关键后台任务（mem0、summary）失败有计数指标。
- Gateway 返回中可选 debug id，便于从 UI 对应 trace。

验收：

- 任意一轮能在 trace 中看出为什么走/不走 rewrite、RAG、Supervisor。
- 后台 mem0/summary 失败不再只能翻日志。

### 10. Path Contract / 路径契约

Agent 的正确性分两层：

1. **Answer correctness**：用户看到的最终回答是否正确。
2. **Path correctness**：系统为得到这个回答走过的路径是否合理、低成本、可控。

真实 trace 中已经出现过“最终结果正确，但路径不合格”的情况：

- 「我生活在哈尔滨」最终 `rag_skipped=true`，回答也可接受；但 rewrite 和 rag_router 都调用了小模型。
- 这种情况如果只看最终输出，会误以为系统没问题；如果看路径，就会发现多花了两次 LLM RTT。

因此每个 turn type 都要有路径契约。

路径契约字段建议：

| 字段 | 含义 |
|------|------|
| `turn_type` | 本轮分类，如 `fact_update`、`knowledge_query` |
| `fast_path` | 是否走快速路径 |
| `rewrite.should_call` / `rewrite.called` | rewrite 是否应该调用 / 实际是否调用 |
| `rag_router.should_call` / `rag_router.called` | router LLM 是否应该调用 / 实际是否调用 |
| `rag.should_call` / `rag.called` | RAG 是否应该检索 / 实际是否检索 |
| `supervisor.should_call` / `supervisor.called` | Supervisor/deepagents 是否应该调用 / 实际是否调用 |
| `llm_call_count` | 本轮 LLM 调用次数 |
| `fallback_count` | 本轮 fallback 次数 |
| `path_contract` | `pass` / `fail` |
| `path_contract_reason` | 失败原因，如 `unexpected_rewrite_llm` |

示例契约：

| 输入 | 期望路径 |
|------|----------|
| 我出生于1997年 | `turn_type=fact_update`；0 次 LLM；0 次 RAG；模板确认 |
| 我生活在哈尔滨 | `turn_type=fact_update`；不调用 rewrite/router/Supervisor |
| 你好 | `turn_type=chitchat`；不调用 RAG；模板或小模型 |
| 报销制度是什么 | `turn_type=knowledge_query`；RAG 必须调用；回答应引用来源 |
| 它需要什么材料 | `turn_type=ambiguous`；允许 rewrite；按改写后意图决定 RAG |
| 打开 pageA | `turn_type=client_action`；不调用 RAG；输出 `client_actions` |

落地方式：

1. 在图 state 或 trace metadata 中记录 path metrics。
2. 单元测试不只断言输出，也断言路径字段。
3. LangSmith Dataset 中除 expected answer 外，增加 expected path。
4. 每次优化后同时看 `answer_score` 和 `path_score`。

验收：

- 每个核心 turn type 至少有一条 path contract 测试。
- LangSmith trace 能直接看出 `path_contract=pass/fail`。
- 如果最终答案正确但路径多调用了 LLM，评测仍应判为路径失败。

## 优先级建议

1. `turn_type` + `fact_update` 快速路径。
2. rewrite/router 策略收敛，减少小模型调用率。
3. mem0 小模型配置与注入预算。
4. Path Contract / 路径契约与 trace metadata。
5. 真流式 SSE。
6. Supervisor 简化或双路径。
7. RAG 评测与 sparse 质量提升。
8. 统一 fallback/metrics。

## 已确认决策

1. `fact_update` 直接模板确认，不交给小模型；mem0 写入失败走后台可观测和后续补偿，不阻塞本轮。
2. `chitchat` 走模板或小模型，不继续主模型。
3. 保留 deepagents，但只在复杂任务、规划、多工具或长文档场景启用。
4. 真流式接受句子级/窗口级护栏，必要时做前端撤回/替换。
5. mem0 建议做类别化 schema，但短期保留自由文本并新增归一化视图。
6. RAG 评测建议以 LangSmith Dataset 为主，本地 JSON/Markdown seed 为辅。

## 仍需细化

1. `turn_type` 分类规则优先级和 fallback 策略。
2. 哪些场景属于 deepagents 复杂任务的第一批白名单。
3. `memory_profile` schema 的第一批字段和旧 mem0 事实迁移方式。
4. streaming moderation 的 SSE 事件协议。
5. Path Contract 的第一批字段和测试夹具格式。
6. LangSmith Dataset 的字段结构和本地 seed 同步方式。

## 验收指标草案

| 指标 | 目标 |
|------|------|
| fact_update LLM 调用数 | 0 |
| fact_update P95 | < 500ms（不含网络代理） |
| rewrite 小模型调用率 | 明显低于当前基线 |
| router 小模型调用率 | 仅规则不确定时触发 |
| 首 token 时间 | 普通回答显著低于完整响应时间 |
| Supervisor 平均输入 token | 较当前 trace 下降 |
| mem0 注入 facts | 默认不超过配置上限 |
| path_contract pass rate | 核心评测集接近 100% |
