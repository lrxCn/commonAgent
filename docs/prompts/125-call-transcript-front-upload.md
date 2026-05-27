# 125 - 通话转写：Front 挂断上报

## 建议执行模型

- 模型：GPT-5 或同档强编码模型
- Reasoning：medium
- 原因：需与 `asr.ts` 生命周期、`call` store 元数据对齐并抽共用 payload 构建逻辑。

## 新窗口执行规则

1. 先读 `AGENTS.md`、`README.md`、`docs/progress.md` 与本任务卡。
2. 阅读 PRD：[call-transcript-persistence.md](../prd/call-transcript-persistence.md)；阅读 `front/src/stores/asr.ts`、`front/src/stores/call.ts`。
3. 核对 **124** 已完成（Back POST 可用）；可用 mock 或本地 Back 联调。
4. 只实现 Front 上报；不改 Agent、不改 Back internal（**126**）。
5. `npm run build` 与相关 vitest 通过后更新 progress **125** → `✅`。
6. 自动 git commit；不 push。

## 依赖

124

## 背景

`dumpTranscriptToConsole` 已具备排序与 `trackRoleLabel`；本任务抽出同源 `buildTranscriptPayload()`，在 `stopAll` 后 **fire-and-forget** POST（失败不阻断通话结束；至少 `console.warn`）。

## 目标

- `front/src/api/calls.ts`（或扩展现有 calls API）：`postCallTranscript(callId, body)`。
- `front/src/stores/asr.ts`：`buildTranscriptPayload()` + `persistCallTranscript()`；`finalLines.length === 0` 时跳过。
- 元数据来自 `sessionCallId`、`callStore`（`peerUserId`、`peerDisplayName`、`callStartedAt`）、`duration_ms` 与 console 一致。
- `lines[]` 含 `role_label`（与 console 标签一致）。
- 单测：payload 排序/标签；空 lines 不调用 API（mock fetch/http）。

## 范围

| 模块 | 变更 |
|------|------|
| `front/src/stores/asr.ts` | 抽取 payload；挂断 persist |
| `front/src/api/calls.ts` | POST client |
| `front/src/types/call.ts` 或 `asr.ts` | 请求/响应类型（如需） |
| `front/src/stores/asr.test.ts` 或 `*.test.ts` | payload / 跳过逻辑 |

## 实施步骤

1. 将 `dumpTranscriptToConsole` 内排序逻辑复用到 `buildTranscriptPayload()`。
2. 实现 `persistCallTranscript`：调用 `POST /api/calls/${callId}/transcript`（Cookie 由现有 `http` 客户端携带）。
3. 在 `stopAll` 中：`dump` 之后调用 persist（`void persistCallTranscript(...).catch(...)`）。
4. 无 `sessionCallId` 或空 lines 时 no-op。
5. `cd front && npm run build`；`npm test` 或 `vitest run`（按项目脚本）。

## 验证方案

```bash
cd front && npm run build
cd front && npm test
```

手工（可选）：双浏览器通话 → 挂断 → Back DB / 或 Network 见 POST 201。

## 非范围

- Agent tool（**126**）
- CallsView 历史列表 UI
- 自动 Chat / langmem
- README 收口（**127**）
- 修改 ASR 实时路径或 console dump 行为（保留 dump）

## 完成标准

- [ ] 挂断且有 final 句时发起 POST；无内容不 POST。
- [ ] payload 与 console 分角色稿一致。
- [ ] front build（+ 单测若新增）绿。
- [ ] progress **125** → `✅`。
- [ ] git commit。

## 进度更新

`docs/progress.md` **125** → `✅`；建议下一步 **126** 或 **127**（若 126 已完成）。
