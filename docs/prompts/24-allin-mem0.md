# 24 - mem0 写入 All-in（`infer=True`）

## 依赖

07, 17

## 背景与动机

第一期任务 **17** 采用 **应用层提取 + `Memory.add(..., infer=False)`**：每轮用 `mem0_extract.txt` 调 LLM 抽事实，再包成 `User preference facts:\n- ...` 写入 Qdrant。

该路径存在 **记忆重复写入（memory deduplication）** 问题：

- 每轮 post_turn 都会再跑提取；回忆型轮次（如「我叫什么名字」）可能从 **助手回复** 再次抽出已存在事实。
- `infer=False` 时 mem0 **不做** 已有记忆检索与 hash 去重，相同 `data` 会生成多个 Qdrant point（`hash` 相同、`created_at` 不同）。

本任务改为 **路线 A**：写入完全交给 mem0 **`infer=True`** 管线（检索 → LLM 抽取 → hash 去重 → 写入），应用层 **不再** 自研提取 LLM。

> 任务 **07**（读取）、**17**（post_turn 触发时机）的契约不变；**不修改** `docs/prompts/07-*.md`、`17-*.md` 原文，以本文为准描述写入侧演进。

## 目标

- post_turn 仍将 **本轮对话**（`user` + `assistant` 原文）交给 `Memory.add`，且 **`infer=True`**。
- 依赖 mem0 内置：**向量检索已有记忆**、**抽取**、**`md5(text)` hash 去重**，避免语义相同事实重复落库。
- 抽取规则通过 mem0 **`custom_instructions`**（或 `add(..., prompt=...)`）配置，**禁止**再跑一遍应用层 `mem0_extract.txt` + 第二遍 mem0 抽取（双 LLM）。

## 范围

| 模块 | 变更 |
|------|------|
| `agent/src/memory/mem0_write.py` | 见下文「实现要点」 |
| `agent/src/memory/mem0_client.py` | `build_mem0_config` 增加 `custom_instructions`（新文件见下） |
| `agent/src/memory/prompts/mem0_custom_instructions.txt` | **新建**：面向 mem0 _additive_ 抽取的英文/中文规则（勿复用带 `{turn_text}` 占位符的 `mem0_extract.txt`） |
| `agent/tests/test_mem0_write.py` | 断言 `infer=True`、payload 为原始 turn 消息列表 |
| 根目录 `README.md` | 写入语义同步（由 skill/人工随实现更新） |
| `docs/prd1.md` | 用户偏好写入一句同步 |
| `docs/progress.md` | 本任务行状态 |

## 非范围

- mem0 **读取** API（`fetch_user_memories` / `format_mem0_for_system`）签名不变。
- `post_turn.py` 调度方式不变（仍 fire-and-forget）。
- mem0 托管云 / `MemoryClient`（仍禁止）。
- 用户删记忆 API、读侧语义去重、离线 consolidation job（可放后期 todo）。
- 修改任务卡 **07**、**17** 文件内容。

## 实现要点

### 1. 禁止「只改 infer 标志」

**错误做法**：保留 `extract_facts_from_turn` → `build_mem0_add_payload` → `add(..., infer=True)`。

**正确做法**：

```text
turn_messages (HumanMessage + AIMessage)
  → turn_messages_to_mem0_payload()  # [{role, content}, ...]
  → memory.add(messages, user_id=..., infer=True)
  → parse results[].memory 作为返回值（可选日志）
```

### 2. 删除或移出写入热路径的代码

从 `extract_and_store` 调用链移除（可保留仅供单测的 legacy 函数，但默认路径不得使用）：

- `_invoke_extractor` / `set_mem0_extract_llm`
- `extract_facts_from_turn`
- `build_mem0_add_payload`（`User preference facts:` 包装）

### 3. `custom_instructions`

在 `mem0_client.build_mem0_config` 中加载 `prompts/mem0_custom_instructions.txt`，映射到 mem0 `MemoryConfig.custom_instructions`。

建议规则（与旧 `mem0_extract.txt` 对齐）：

- 只记 **稳定偏好 / 画像**（姓名、语言、格式、习惯等），不记一次性问答。
- **仅从 user 消息抽事实**；用户问「我叫什么」、助手答姓名时 **不得** 再 ADD 姓名。
- 与用户输入 **同语言** 记录事实。
- 无事实时 mem0 返回空 `memory` 列表。

### 4. 读取与存储格式变化

| 阶段 | Qdrant `payload.data` 示例 |
|------|---------------------------|
| 旧（`infer=False`） | `User preference facts:\n- 用户姓名：刘日兴` |
| 新（`infer=True`） | 短句事实，如 `用户名叫刘日兴`（由 mem0 生成，非固定格式） |

`get_all` → `memory` 字段解析 **无需改**；但 **旧数据与新数据 hash 不同**，迁移前可能短期并存。

### 5. 数据迁移（实现本任务时必做其一）

上线前对开发/测试环境 `QDRANT_COLLECTION_MEM0`：

- **推荐**：按 `user_id` 清空或重建 collection，避免旧包装文本与新短句并存。
- **或**：一次性脚本删除 `data` 以 `User preference facts:` 开头的 point。

生产 rollout 时在 README / runbook 写明步骤。

### 6. 运维说明

- mem0 默认在 `~/.mem0/history.db`（或 `MEM0_DIR`）存会话辅助；向量仍在 Qdrant。多实例部署时文档注明 SQLite 路径策略。
- 每轮 post_turn 增加 **1 次 mem0 内部 LLM + 检索**（替换原应用层提取 LLM，**不得** 两者叠加）。

### 7. 与架构图一致

异步写入仍在 `post_turn_jobs_node` 之后，不阻塞首 token（见根目录 [README.md](../../README.md) 的单轮流水线）。

## 测试方案

```bash
cd agent
uv run pytest tests/test_mem0_write.py tests/test_mem0_read.py -v
```

| 用例 | 期望 |
|------|------|
| `extract_and_store` mock `Memory.add` | `infer=True`；`messages` 含 `user`/`assistant` 原文，**无** `User preference facts` 前缀 |
| `MEM0_MOCK=true` | 不调用 `add` |
| 集成（本地 Qdrant，可选） | Turn1 自我介绍 → 1 条；Turn2 仅问姓名 → **不新增** 同 hash 记录 |

## 完成标准

- [ ] 写入路径仅 `infer=True` + 原始 turn messages。
- [ ] `custom_instructions` 已配置且单测/手工验证 Turn2 不重复写入。
- [ ] `test_mem0_write.py` 全部通过。
- [ ] 根目录 `README.md`、`prd1.md` 记忆表、本任务在 `progress.md` 标为 ✅。
- [ ] 迁移说明写入根目录 `README.md`（或本任务卡「数据迁移」已执行并记录）。

## 验证清单（手工）

1. Turn1：`我叫刘日兴` → Qdrant 1 条，无 `User preference facts:` 包装。
2. Turn2：`我叫什么名字` → 能答对，且 **无** 第二条同义记忆。
3. LangSmith：每轮 post_turn **仅一条** mem0 相关 LLM span（非双提取）。

## 进度更新

`docs/progress.md` **24** → 实现完成后改为 `✅`。
