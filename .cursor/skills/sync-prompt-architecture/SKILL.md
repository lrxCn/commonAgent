---
name: sync-prompt-architecture
description: Keeps docs/architecture.md aligned when docs/prompts task cards are revised, fixed, or temporarily changed because the original prompt was unreasonable. Use when editing prompts/*.md, saying "改一下任务卡/ prompt 不合理", "同步架构", or after materially changing scope, APIs, memory rules, RAG flow, or client_actions in a prompt. Does not implement code—documentation consistency only.
paths:
  - "docs/prompts/**/*.md"
  - "docs/prompts/*.md"
  - "docs/architecture.md"
---

# Prompt 修订 → 同步 architecture（commonAgent）

用户修改 `docs/prompts/` 任务卡时（尤其因 **不合理而临时调整**），必须把 **`docs/architecture.md`** 同步为**当前真实设计**。任务卡是落地细则，architecture 是跨任务的**总契约**；二者冲突时以**改后的 prompt + 用户口头确认**为准，并回写 architecture。

本 skill **只改文档**，不实现业务代码（除非用户另行要求）。

## 与 `execute-prompt-task` 的分工

| Skill | 何时用 |
|-------|--------|
| **execute-prompt-task** | 按任务卡写代码、跑测试、更新 progress |
| **sync-prompt-architecture**（本 skill） | 只改了任务卡/架构叙述，需对齐 architecture（及必要时 prd1、其它 prompt） |

若用户同时要「改 prompt + 写代码」，先完成本 skill 的文档同步，再执行 `execute-prompt-task`。

## 0. 触发与输入

确认变更来源：

- 用户 `@` 了某张 `docs/prompts/XX-*.md`
- 或说明了要改的任务 ID / 不合理之处
- 或已存在未提交的 prompt diff

无法确定改了哪张卡时，先问用户或 `git diff docs/prompts/`。

## 1. 判断：要不要动 architecture？

### 必须同步到 architecture（契约级变更）

任一出现即**必须**改 `docs/architecture.md`：

- 三层边界、鉴权责任、Agent 是否内网
- 记忆分层、K/M/summary 规则、context vs checkpoint state
- 单轮流水线顺序（护栏、rewrite、RAG、Supervisor、异步项）
- RAG：路由策略、rewrite→RAG 顺序、二查条件、ingest 规则
- `client_actions` 语义（执行方、是否 resume、checkpoint 形态）
- **API 路径、请求/响应字段、SSE 事件格式**
- 目录结构目标态、模块职责表
- 默认常量（如 K=4、M=20、分块大小）若任务卡与 architecture 不一致
- 新增/删除/合并任务导致的**全局能力**变化（见 §12 任务索引）

### 通常不必改 architecture（实现级）

仅改以下内容时，**可只改任务卡**，architecture 不动：

- 具体文件名、`pytest` 用例细节、本地端口
- mock 开关名、单测数据
- README 措辞、命令示例

**拿不准时**：倾向**小改 architecture**（一句注记或表格一格），避免后人只读 architecture 得到过期契约。

## 2. 同步流程（按序执行）

### 2.1 读基准

1. [docs/architecture.md](../../docs/architecture.md) — 当前总契约
2. [docs/prd1.md](../../docs/prd1.md) — 产品需求源（arch 不应长期与 prd 矛盾）
3. **被改的任务卡**及受其影响的**下游任务卡**（看 **依赖** 节）

### 2.2 做差异分析

用简短列表写出「prompt 改后 vs architecture 现文」差异，标出：

- **改 architecture 的哪一节**（见下表）
- 是否影响其它 prompt（列出 ID）
- 是否与 prd1 冲突

| architecture 章节 | 典型对应 prompt 内容 |
|-------------------|----------------------|
| §1 目标与边界 | 层级职责、硬约束 |
| §2 逻辑架构 | 新模块/节点、mermaid 边 |
| §3 目录结构 | 新目录、包路径约定 |
| §4 记忆分层 | K/M、summary、mem0、注入位置 |
| §5 单轮流水线 | 节点顺序、并行、异步 |
| §6 RAG | 路由、检索、ingest、二查 |
| §7 client_actions | 工具语义、JSON 示例 |
| §8 API 契约 | Gateway 路径与 body |
| §9 模块职责 | 模块表 |
| §10 可观测与安全 | LangSmith、环境变量原则 |
| §11 后期 todo | 明确推迟项 |
| §12 任务索引 | 任务数量/阶段描述（非逐条勾选） |

### 2.3 修改 architecture.md

原则：

- **最小 diff**：只改受影响段落；不整篇重写
- **保留 mermaid** 与表格风格与原文一致
- 若任务卡是**临时折中**（用户明确说「先这样」），在相关节末加 blockquote：

  `> **临时约定（YYYY-MM-DD）**：…… 原因：…… 计划在任务 XX 还原。`

- 默认常量、API 示例与改后的 prompt **逐字一致**
- §12 仅反映阶段级变化，不替代 [progress.md](../../docs/progress.md)

### 2.4 连带文档（按需）

| 情况 | 动作 |
|------|------|
| 变更属产品需求 | 询问是否同步 [prd1.md](../../docs/prd1.md)；用户同意则改 |
| 变更影响其它任务卡 Scope/API | 列出受影响 ID，**询问**是否一并改 prompt；用户同意则改 |
| 仅实现细节 | 不改其它 prompt |
| 任务卡新增/删除全局能力 | 更新 architecture §12；**建议**用户决定是否增删 `docs/prompts/` 文件并改 progress 表 |

### 2.5 更新 progress（轻量）

在 [docs/progress.md](../../docs/progress.md) **变更日志**追加一行（不改动任务 ✅/⬜ 除非用户要求）：

`日期 | 文档：同步 architecture ← 任务 XX（简述改了什么契约）`

## 3. 禁止与注意

- **不要**在未改 prompt 的情况下单独改 architecture「图好看」
- **不要**让 architecture 与已改 prompt 长期矛盾
- **不要**代替 `execute-prompt-task` 标任务完成或跑测试
- **不要**擅自 `git commit`（除非用户要求）
- 一次对话聚焦**一组相关变更**；多张卡大改时分批同步并说明批次

## 4. 回复用户（中文简体）

1. **变更摘要**（prompt 改了什么、是否契约级）
2. **architecture 改了哪些节**（§ 编号 + 一句话）
3. **其它文件**（prd1 / 其它 prompt / progress 日志）是否动过
4. **风险**：与 prd1 或其它任务卡仍不一致处（若有）
5. **建议下一步**：是否执行 `execute-prompt-task` 或改下游 prompt

## 5. 快速检查清单

```
[ ] 已读改前/改后 prompt 与 architecture 对应节
[ ] 契约级变更已写入 architecture.md
[ ] API/常量/流程图与 prompt 一致
[ ] 临时折中已标注日期与原因（若适用）
[ ] prd1 冲突已告知或已同步
[ ] progress 变更日志已追加
```
