# ppt流程
1. 简介我们来自哪个部门，名字，参赛主题：通用AI Agent落地探索
尊敬的各位领导、各位同事，大家好。我们是来自公专融合-通信平台BU-MCS产品部的刘日兴、陈可新。我们团队的参赛题目是：通用AI Agent落地探索。
2. 开篇点题，我们for大赛的产品力提升创新部分
本次比赛，我们选择的方向是公告中提到的【产品力提升创新】。(配合PPT动效框选)
依托当前AI技术高速发展的大环境，我们结合了公司的业务现状，和行业内前沿的流行技术方案，尝试沉淀出一套低门槛、高复用的AI agent底层接入方案。
3. 综述
希望借这次比赛的契机，抛砖引玉，尝试探索出一条通用智能体（Agent）落地多业务线的最短路径。我们的核心理念是：把我们预想的AI Agent业务落地过程中，各个团队都会面临的通用问题，统一截留在Agent层处理；让业务方能够解放双手，心无旁骛地专注于核心业务逻辑的开发。
我们希望这个项目能作为一块探路石，为公司未来的软件智能化进程积累一点初步经验，也希望能和大家共同探讨未来演进的更多可能。

4. 介绍ppt大纲
接下来的汇报，我们将从以下三个方面展开：
为什么我们需要智能体，我们的智能体做了什么？
AI Agent落地业务的几个场景与示例
在这个过程中看到的障碍与风险

5. 介绍第一章： 为什么我们需要智能体，我们的智能体做了什么？
为什么需要智能体？
要回答这个问题，我们要先看透当前大模型的本质。现阶段的大模型，某种程度上是一个运行在云端、供整个互联网世界使用的“超大型概率计算器”。这种特性决定了它的几个局限性：
上下文窗口有限，无法一次塞入过多问题，即使没塞满，到达上下文窗口30%时就会出现记忆腐化
存在幻觉，不知道的有概率瞎编，回答质量依赖训练数据的质量
缺乏私有状态，作为一个公共大脑，它无法为接入它的每一个应用的每一个用户，单独存储记忆；它也不知道我们的系统里具体有哪些内部工具，更不知道当前提问的用户拥有什么权限
llm就是一个能理解自然语言的http接口，不会执行工具，
【以上需要继续补充llm的缺点，agent存在的必要性】
Agent，也就是智能体，正是为了填补这些空白而生的“人类使用AI的适配层”。我们平时接触到的 Cursor 写代码、豆包 P图、千问点奶茶，背后都是 Agent 在起作用。
大模型是一个没有手脚、没有记忆、不知道你是谁的大脑——Agent就是给它装上手脚、接上记忆、赋予它身份的那层适配。

6. 我们做了什么
为了解决上面提到的问题，我们的课题就是打造一个生产可用的AI Agent，
下面是具体的架构图


flowchart TD
  START([START]) --> intake["intake_input<br/>接收用户目标与上下文"]

  intake --> load_memory["load_memory<br/>加载短期/长期/实体记忆"]
  load_memory --> context_budget["context_budget_check<br/>检查上下文窗口"]

  context_budget -->|上下文过长| compress_memory["compress_memory<br/>滑动窗口 + 摘要 + 重要性过滤"]
  context_budget -->|上下文正常| intent_router["intent_router<br/>判断任务类型与复杂度"]
  compress_memory --> intent_router

  intent_router -->|简单问答| direct_answer["direct_answer<br/>直接回复"]
  intent_router -->|需要工具/外部信息| react_loop["react_agent<br/>ReAct 推理循环"]
  intent_router -->|复杂目标| planner["planner<br/>Plan-and-Execute 任务拆分"]
  intent_router -->|专业分工/并行任务| orchestrator["multi_agent_orchestrator<br/>多 Agent 编排"]

  direct_answer --> reflection_gate["reflection_gate<br/>是否需要质量检查"]

  react_loop --> tool_router["tool_router<br/>选择工具"]
  tool_router --> tool_exec["tool_executor<br/>执行工具并校验参数"]
  tool_exec --> observation["observation<br/>写入工具结果"]
  observation --> react_continue{"是否继续 ReAct?"}
  react_continue -->|继续| react_loop
  react_continue -->|完成| reflection_gate
  react_continue -->|超过 max_steps| fallback["fallback_handler<br/>降级/澄清/返回部分结果"]

  planner --> plan_validate["plan_validate<br/>校验子任务/依赖/验收标准"]
  plan_validate --> execute_plan["execute_plan<br/>执行计划步骤"]
  execute_plan --> step_router{"步骤类型"}
  step_router -->|普通 LLM 步骤| llm_step["llm_step_executor"]
  step_router -->|工具步骤| tool_router
  step_router -->|需要专业 Agent| orchestrator

  llm_step --> step_observe["step_observe<br/>记录中间结论"]
  step_observe --> plan_done{"计划完成?"}
  observation --> plan_done
  plan_done -->|未完成| execute_plan
  plan_done -->|完成| reflection_gate

  orchestrator --> agent_router["agent_router<br/>选择 Worker Agent"]
  agent_router --> researcher["researcher_agent"]
  agent_router --> coder["coder_agent"]
  agent_router --> reviewer["reviewer_agent"]
  agent_router --> memory_manager["memory_manager_agent"]

  researcher --> agent_result["agent_result_aggregate<br/>聚合子 Agent 结果"]
  coder --> agent_result
  reviewer --> agent_result
  memory_manager --> agent_result

  agent_result --> multi_done{"多 Agent 任务完成?"}
  multi_done -->|未完成/需切换| orchestrator
  multi_done -->|完成| reflection_gate

  reflection_gate -->|不需要反思| memory_write["memory_write<br/>写入长期/实体记忆"]
  reflection_gate -->|需要反思| evaluator["evaluator<br/>事实/完整性/约束/格式检查"]

  evaluator --> eval_pass{"PASS?"}
  eval_pass -->|通过| memory_write
  eval_pass -->|未通过且未超过轮次| revise["revise<br/>按评估意见修正"]
  eval_pass -->|超过 max_reflection_rounds| fallback

  revise --> reflection_gate

  fallback --> memory_write
  memory_write --> final_answer["final_answer<br/>输出最终结果"]
  final_answer --> END([END])

【这个图也不完整，没展示o11y,没展示rag】

7. 技术选型与实现方案
langchain+langgraph
python
postgres + checkpointer负责短期记忆
graphiti负责长期记忆，实体记忆、语义记忆、情景记忆
rag做向量数据库

8. 与业务方对接

9. 对接案例：AI Agent落地业务的几个场景与示例

10. 问题与机会
作为一个软件开发者，在探索落地的过程中，我看到了明显的障碍，但也看到了巨大的机会。

11. 落地障碍
落地障碍：私有化部署的成本
在我们专业通信领域，因为极高的安全保密要求，大模型通常需要本地私有化部署，而动辄百万的 GPU 算力成本是业务落地的第一只拦路虎。
我认为，必须从技术和业务双管齐下寻找高性价比的破局点：
- 技术上： 我们正在通过优化 Agent 架构、引入量化剪枝技术，让原本沉重的大模型变得轻量化；同时通过模型微调（Fine-tuning），让一个“普适”的模型，成为懂我们专业通信领域的“专家”。


12. 最大的问题
最大的机会：专业领域的数据壁垒
分享一个我上家公司的经历。我之前做过智慧农业，美国的大农场模式农业，在50年前就开始积累土壤、种子、气候等农业数据；而我们国家想发展智慧农业，卡脖子的第一关往往是“没有高质量的历史数据供我们研究”。
换到我们的专业通信领域，情况也是相似的。
当前通用大模型的发展已经逼近瓶颈，因为互联网上人类积累的公开数据快被“吃光了”。但在专业通信这个垂直领域，高质量的AI训练数据还没有被挖掘使用。
我们的软件系统部署在客户的私有化机房里，最核心的数据在客户手里。受限于隐私我们拿不到原数据。但如果我们能转变思路，采用类似“联邦学习”或端侧训练的模式：在客户机房利用本地数据进行微调训练，训练结束后只把“变聪明的模型权重和经验”带回来。
如果能走通这条路，我们就能利用独有的专业领域数据，构建出真正具备行业壁垒的通信大模型，这背后的商业想象空间是巨大的。

13. 未来产品的演进方向
我觉得未来的产品形态变迁会经历下面3个过程
1. 左侧网站，右侧ai聊天框
2. 只有聊天框
3. 每个公司只输出mcp，用户人手一个codex，我们的mcp被codex调用
就像人手一台智能手机之后，我们做app一样

