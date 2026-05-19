---
name: execute-prompt-task
description: Executes a single implementation task from docs/prompts/*.md for the commonAgent project. Use when the user opens, @-mentions, or asks to run a file under docs/prompts/ (e.g. docs/prompts/01-project-init.md), or says "执行这个 prompt/任务卡". Reads docs/architecture.md and docs/progress.md first, implements the task, runs the prompt's test plan, then updates progress.
paths:
  - "docs/prompts/**/*.md"
  - "docs/prompts/*.md"
---

# 执行 Prompt 任务卡（commonAgent）

你正在执行 `docs/prompts/` 下的**单张**任务卡。一次只完成一张；不要顺带做其他序号 unless 用户明确要求。

## 0. 识别当前任务

从用户消息或当前打开文件解析任务 ID 与路径，例如：

- `docs/prompts/05-gateway-minimal.md` → 任务 **05**

若无法确定，询问用户要执行哪张任务卡。

## 1. 必读文档（在任何代码修改之前）

按顺序阅读并遵守：

1. [docs/architecture.md](../../docs/architecture.md) — 总体架构与契约
2. [docs/progress.md](../../docs/progress.md) — 当前进度与依赖
3. **当前任务卡** `docs/prompts/XX-*.md` — 本任务唯一范围

核对任务卡 **依赖** 节：依赖项在 `progress.md` 中必须为 `✅`。若有未完成依赖：

- 告知用户应先完成哪张任务卡
- **停止实现**（除非用户明确说跳过依赖）

可选参考：[docs/prd1.md](../../docs/prd1.md)

若本任务卡刚被修订（范围/API/流程与 architecture 不一致），先走 [sync-prompt-architecture](../sync-prompt-architecture/SKILL.md) 同步 `docs/architecture.md`，再写代码。

## 2. 执行实现

严格按任务卡执行：

| 章节 | 要求 |
|------|------|
| **目标** | 必须达成 |
| **范围** | 只做列出的内容 |
| **非范围** | 禁止扩张 |
| **实现要点** | 技术决策以此为准 |
| **产出文件** | 逐项勾选 |

### 项目约定（来自 origin / architecture）

- 技术栈：deepagents、Python、uv、Postgres、Qdrant、mem0
- 修改 `.env` 必须同步 `.env.example`，示例值用掩码
- `user_id` / `role_id` / `tools[]` 在每轮 **request context**，不写死进 checkpoint state
- 外部工具只产出 `client_actions`，不执行、不 resume
- 能用 deepagents 内置则不重复造轮子

### 工作方式

1. 先查看仓库现状，避免覆盖已有正确实现
2. 小步提交式修改：优先匹配现有目录（见 architecture §3）
3. 任务卡若与仓库实际路径不一致，以**已有结构**为准，并在进度备注中记一笔

## 3. 运行测试方案（必须）

完成任务卡 **测试方案** 中的所有命令：

- 在项目根或 `agent/` / `back/` / `front/` 下执行
- 需要 Postgres / Qdrant 而本地无服务时：运行 mock/单元测试；在进度 **备注** 写明 `integration skipped: ...`
- **任一命令失败**：修复后重试；仍失败则**不要**把任务标为完成，向用户报告错误与日志

测试通过后，在回复中简要列出：跑了哪些命令、结果如何。

## 4. 更新进度文档（测试通过后）

编辑 [docs/progress.md](../../docs/progress.md)：

1. 将对应 **ID** 行的状态改为 `✅`，填写 **完成日**（YYYY-MM-DD）
2. **备注** 可写：关键文件路径、跳过的 integration、已知 todo
3. 更新 **总览** 表格：已完成数量、**当前建议下一步**（第一张非 ✅ 的依赖已满足的任务）
4. 在 **变更日志** 追加一行：`日期 | 完成任务 XX：一句话`

不要将未通过测试的任务标为完成。

## 5. 回复用户

用中文简体，结构建议：

1. **完成了什么**（1–3 句）
2. **关键文件**
3. **测试结果**
4. **下一步建议**（下一张任务卡链接）

若用户只 `@` 了任务卡但未说「开始」，先确认是否立即执行；若上下文已明确要执行，直接开始。

## 6. 禁止事项

- 不要一次完成多张任务卡
- 不要跳过测试就更新 progress
- 不要提交 `.env` 或真实密钥
- 不要擅自 `git commit`（除非用户要求）
- 不要实现任务卡 **非范围** 中的后期 todo

## 快速命令参考

```bash
# 解析任务号
basename "docs/prompts/05-gateway-minimal.md"  # → 05-gateway-minimal.md

# 常见 agent 测试
cd agent && uv sync && uv run pytest -v

# 读进度
rg "^\| 05 " docs/progress.md
```
