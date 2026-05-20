# 25 - State 精简：移除 `mem0_text`，改写阶段再格式化

## 依赖

13.5, 09, 12

## 背景与动机

任务 **13.5** 将 `mem0_memories` 与 `mem0_text` 均列入 `AgentState`（`EphemeralValue`），由 `load_memory_node` 同时写入：

- `mem0_memories`：`fetch_user_memories` 返回的 **事实列表**（canonical）。
- `mem0_text`：`format_mem0_for_system(mem0_memories)` 的 **Markdown 块**（派生视图）。

该设计存在以下问题：

1. **违反单一事实源**：同一轮数据以 list + string 两种形态并存，`_resolve_mem0_text` 的 fallback 也表明二者可能不一致。
2. **节点职责错位**：`load_memory` 应是 I/O（读 mem0 + checkpoint + summary），不应为下游 **rewrite prompt** 预组装展示层字符串。
3. **重复格式化**：`context_assembly` / `build_system_prompt` 已接收 `mem0_memories` 并再次调用 `format_mem0_for_system`，与 `load_memory` 内格式化重复。

对比其它单轮字段：`rewritten_query`、`system_prompt` 均由 **消费节点** 产出；`mem0_text` 却由 **上游加载节点** 为 rewrite 预计算，不对称。

> 任务 **07**（mem0 读取 API）、**09**（rewrite 语义）、**12**（system 组装）行为不变；**不修改** `07-*.md`、`09-*.md`、`12-*.md`、`13.5-*.md` 原文，以本文为准描述 state 侧演进。

## 目标

- `AgentState` **仅保留** `mem0_memories: list[str]` 作为 mem0 读取结果在图中的传递通道。
- **删除** `mem0_text` 键（及所有写入/读取/ carry 列表中的引用）。
- **rewrite 阶段**在节点内调用 `format_mem0_for_system(mem0_memories)`（或局部变量 `mem0_block`）填入 `rewrite.txt` 的 `{mem0_text}` 占位符；**不**再依赖 state 中的 `mem0_text`。
- `load_memory_node` **只写** `mem0_memories`（及 `rolling_summary`、`messages` 合并逻辑等既有字段）。

## 范围

| 模块 | 变更 |
|------|------|
| `agent/src/graph/state.py` | 移除 `mem0_text` 字段 |
| `agent/src/graph/nodes.py` | `load_memory` 不再写 `mem0_text`；`rewrite_graph_node` 不再向 payload 传 `mem0_text`；`_CARRY_KEYS` 等列表去掉 `mem0_text` |
| `agent/src/rag/rewrite.py` | `rewrite_node` 从 `mem0_memories` 格式化；删除 `_resolve_mem0_text`；`RewriteState`（若有）去掉 `mem0_text` 或改为仅 `mem0_memories` |
| `agent/src/observability/tracing.py` | rewrite span metadata：由 `mem0_memories` 推导 `mem0_text_len`（或 `mem0_facts_count`），勿读 state 中已删除的键 |
| `agent/tests/test_rewrite.py` | 用例改为传 `mem0_memories`；断言 prompt 中含格式化块 |
| `agent/tests/test_graph_*.py` | 若有 `mem0_text` 断言则更新 |
| `docs/architecture.md` §3.1 | state 字段表同步（目标态） |
| `docs/progress.md` | 本任务行状态 |

## 非范围

- 修改 `format_mem0_for_system` 的 Markdown 模板（除非测试断言需要）。
- mem0 读/写 API、`MEM0_MOCK`、任务 **24** 写入管线。
- 为 Studio 调试 **重新** 在 state 中暴露 `mem0_text`（若需要，应由 `rewrite_node` **可选** 写回调试键，本任务默认不做）。
- 修改历史任务卡 **13.5** 文件正文（architecture 以新契约为准）。

## 实现要点

### 1. `load_memory_node`（只读、只写 canonical）

```text
fetch_user_memories(user_id) → mem0_memories
# 禁止：mem0_text = format_mem0_for_system(...)
return { "mem0_memories": mem0_memories, ... }
```

### 2. `rewrite_node`（消费方格式化）

```text
memories = state["mem0_memories"] or []
mem0_block = format_mem0_for_system(memories)  # 空列表 → ""
prompt = build_rewrite_prompt(user_message, mem0_block, recent_messages)
# rewrite.txt 仍使用占位符名 mem0_text={mem0_block}，无需改模板文件名
```

- `rewrite_query(...)` 函数签名可保留参数名 `mem0_text: str`（表示 **已格式化的块**，由调用方传入），或重命名为 `mem0_block` 并在任务内统一；**禁止** 再要求调用方从 graph state 读取 `mem0_text` 键。

### 3. `context_assembly`（无变更逻辑）

- 继续 `build_system_prompt(mem0=state["mem0_memories"])`，内部已有 `format_mem0_for_system`。
- 确认无代码路径依赖 `state["mem0_text"]`。

### 4. 删除 `_resolve_mem0_text`

- 移除「`mem0_text` 优先、否则从 `mem0_memories` 再 format」的分支，避免掩盖 state 双写问题。

### 5. 观测（LangSmith）

- `rewrite` span：`mem0_facts_count=len(memories)`，`mem0_text_len=len(mem0_block)`（在 rewrite 内计算后写入 metadata）。
- 不要求 graph checkpoint / `get_state` 含 `mem0_text`。

### 6. 与 EphemeralValue 原则对齐

- **State 存事实**（`mem0_memories`）。
- **各消费节点自格式化**（rewrite、assembly 各调一次 `format_mem0_for_system`；允许重复调用，禁止重复 state 键）。

## 测试方案

```bash
cd agent
uv run pytest tests/test_rewrite.py tests/test_graph_invoke_mock.py tests/test_graph_compile.py -v
```

| 用例 | 期望 |
|------|------|
| `rewrite_node` + `mem0_memories=["偏好简洁"]` | prompt / mock LLM 输入含 `## User preferences` 与 `- 偏好简洁` |
| `rewrite_node` + 空 `mem0_memories` | mem0 块为 `（无）` 或等价空态（与现 `rewrite.txt` 一致） |
| `load_memory` mock | 返回 state 更新 **无** `mem0_text` 键 |
| 图 invoke smoke | 全流程不访问 `state["mem0_text"]` |

## 完成标准

- [ ] `AgentState` 无 `mem0_text`。
- [ ] `load_memory` 仅写 `mem0_memories`。
- [ ] rewrite 从 `mem0_memories` 格式化；`_resolve_mem0_text` 已删除。
- [ ] 上述 pytest 通过。
- [ ] `architecture.md` §3.1、`progress.md` 任务 25 标为 ✅。

## 验证清单（手工，可选）

1. LangSmith 一轮对话：rewrite span metadata 含 `mem0_facts_count` / `mem0_text_len`，图中 state 快照无 `mem0_text`。
2. 带 mem0 偏好用户问指代消解问题，改写结果仍合理。

## 进度更新

`docs/progress.md` **25** → 实现完成后改为 `✅`。
