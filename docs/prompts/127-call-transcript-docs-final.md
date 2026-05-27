# 127 - 通话转写：README、PRD 落地与演示收口

## 建议执行模型

- 模型：GPT-5 或同档轻量文档模型
- Reasoning：low
- 原因：以契约同步、演示脚本与 progress 为主；实现已在 124–126 完成。

## 新窗口执行规则

1. 先读 `AGENTS.md`、`README.md`、`docs/progress.md` 与本任务卡。
2. 核对 **124**、**125**、**126** 均为 `✅`；快速扫一眼已实现 API/tool 与 PRD 是否一致。
3. 只改文档与演示脚本；**不改**业务逻辑，除非文档与代码明显不一致需一行修正。
4. 运行 smoke：`back` transcript 相关 pytest + `front` build。
5. 更新 progress **127** → `✅`；通话转写批次收口。
6. 自动 git commit；不 push。

## 依赖

124, 125, 126

## 背景

[call-transcript-persistence.md](../prd/call-transcript-persistence.md) 初稿时 transcript「不落库」；本批次完成后需在 README 写清 **计划已落地** 的运行契约，并更新 PRD「落地状态」。

## 目标

- **README.md**：三层表、Back API（`POST .../transcript`、`/internal/calls/transcripts`）、Front 挂断上报、Agent tool 名称与边界（不进 langmem/Qdrant）；修正「挂断仅 console、不落库」表述。
- **PRD** `call-transcript-persistence.md`：增加「落地状态」表；链接任务 **124–127**。
- **demo-walkthrough.md**（可选 **B7**）：双浏览器通话 → 挂断 → Chat 问「刚才电话说了什么」手工步骤。
- **docs/maps/demo-platform.md**（若存在通话/asr 段）：补 persist + tool 一句。
- **docs/progress.md**：批次 **124–127** 摘要、总任务数 127、建议下一步恢复为 buglist/B6 等。

## 范围

| 文件 | 变更 |
|------|------|
| `README.md` | 契约 |
| `docs/prd/call-transcript-persistence.md` | 落地状态 |
| `docs/demo-walkthrough.md` | 可选 B7 |
| `docs/maps/demo-platform.md` | 可选 |
| `docs/progress.md` | 批次与 127 ✅ |

## 实施步骤

1. 对照代码列出真实路径、字段名、环境变量（`BACK_URL`、`INTERNAL_API_KEY`）。
2. 更新 README Back/Front/Agent 小节，保持与 SAUC PRD 交叉引用。
3. PRD 顶部或文末「落地状态」：124 POST、125 Front、126 tool、已知限制（各存各视角、无向量）。
4. 添加 B7 脚本（简版即可）。
5. Smoke：

```bash
cd back && uv run pytest tests/test_call_transcripts.py tests/test_call_transcripts_internal.py -v
cd front && npm run build
cd agent && uv run pytest tests/test_call_transcript_tools.py -v
```

## 非范围

- 新功能、新 API
- CallsView 历史 UI
- langmem 摘要写入

## 完成标准

- [ ] README 与实现一致；无「仅 console 不落库」过时描述。
- [ ] PRD 含落地状态与任务链接。
- [ ] demo-walkthrough 含 B7 或 README 指向手工步骤。
- [ ] progress 124–127 均为 `✅`，批次收口。
- [ ] smoke 命令绿。
- [ ] git commit。

## 进度更新

`docs/progress.md` **127** → `✅`；**通话转写持久化批次 124–127** 全部完成。
