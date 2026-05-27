# 117 - 火山 SAUC：Front 采集、CallsView 实时字幕与挂断 transcript

## 建议执行模型

- 模型：GPT-5 或同档强编码模型
- Reasoning：medium
- 原因：双轨 PCM 采集（本地麦 + 远端 MediaStream）、Pinia 与 call store 生命周期联动、CallsView 字幕 UI 有中等复杂度；协议已由 Back 封装。

## 新窗口执行规则

1. 先读 `AGENTS.md`、`README.md`、`docs/progress.md` 与本任务卡。
2. 阅读 PRD：[volcengine-streaming-asr.md](../prd/volcengine-streaming-asr.md)「说话人策略」「CallsView 交互」「Front ↔ Back 信令」。
3. 核对 **116** 已完成；阅读 **111–114** 的 `call` store 与 `CallsView.vue`。
4. 只实现 Front ASR store、双轨采集、**CallsView 通话字幕**、挂断 **控制台分角色 transcript**；**不改 ChatDrawer**。
5. `npm run build`（或项目等价命令）通过后更新 progress **117** → `✅`。
6. 自动 git commit；不 push。

## 依赖

116

## 背景

首期 UI **仅通话维度**（PRD 明确）：`in_call` 时在 CallsView 实时展示字幕；挂断后在浏览器控制台打印完整通话文字记录，按 **本地 / 对方** display_name 分角色（双轨 ASR，见 PRD 方案 A）。ASR WebSocket 与 `/api/calls/ws` 分离，与 `useCallSignaling` 并存。

## 目标

- 新增 `front/src/stores/asr.ts`：连接 `WS /api/asr/ws`；处理 `asr.partial` / `asr.final` / `asr.error` / `asr.ended`；支持 `track: local | remote`。
- **双轨采集**（16 kHz mono PCM，binary WS）：
  - **local**：复用 call store 已有 `getUserMedia` 麦克风轨；
  - **remote**：从 `remoteStream` 经 `AudioContext` 分支抽 PCM。
- **CallsView**：`isInCall` 时展示字幕区（partial + final 列表）；ASR 失败不阻断通话。
- **挂断**：`call.hangup` / `call.ended` → stop 双轨 → `console.group` 输出分角色全文（PRD 格式）。
- 与 `call` store 联动：`in_call` 自动 start；`idle` 自动 stop + dump。

## 范围

| 模块 | 变更 |
|------|------|
| `front/src/types/asr.ts` | 信令类型（含 `track`、`scene: call`） |
| `front/src/stores/asr.ts` | WS、双轨状态、transcript 聚合、console dump |
| `front/src/composables/useAsrCapture.ts`（名可调整） | local/remote PCM 重采样 |
| `front/src/views/CallsView.vue` | 通话中字幕 UI |
| `front/src/stores/call.ts` | 挂钩：`in_call` / hangup 通知 asr（最小侵入） |
| `front/vite.config.ts` | 确认 `/api` 代理 `ws: true`（**112** 应已配置） |

## 实施步骤

1. 定义 `AsrClientMessage` / `AsrServerMessage`，与 Back **116** 及 PRD `track` 字段一致。
2. `asr` store：`connect()` 带 Cookie；`startCallTracks(callId, { localLabel, remoteLabel })` 发两路 `asr.start`；`sendAudio(track, ArrayBuffer)`；`stopAll()`。
3. PCM：Worklet 或 ScriptProcessor 重采样至 16 kHz Int16；分片 ~200ms。
4. CallsView：字幕面板样式与 `in-call-panel` 一致；展示合并或分栏 partial/final。
5. 挂断 dump：聚合两轨 final（按 `start_time` 或接收序）；`console.log('[本地 · Alice] ...')` / `[对方 · Bob]`。
6. 错误：`asr.error` 在字幕区展示；**禁止** `VITE_VOLC_ASR_*`。
7. `npm run build`；可选 vitest mock WS。

## 验证方案

```bash
cd front && npm run build
```

手工（需 Back **116** + 火山密钥 + WebRTC **111–114**）：

1. 双浏览器 alice/bob → CallsView 通话 → 双方说话 → 字幕实时更新。
2. 挂断 → 控制台出现 `[Call Transcript]` 分角色全文。
3. Network：`WS /api/asr/ws` + binary 音频帧。

## 非范围

- ChatDrawer 语音输入
- 自动 `POST /api/chat`
- transcript 持久化 / 服务端存储
- README / demo-walkthrough 收口（**118**）
- Agent 改动

## 完成标准

- [ ] CallsView 通话中可看到实时字幕（partial/final）。
- [ ] 挂断后控制台输出分角色完整 transcript。
- [ ] Front 无火山密钥环境变量。
- [ ] `npm run build` 通过。
- [ ] progress **117** → `✅`。
- [ ] git commit。

## 进度更新

`docs/progress.md` **117** → `✅`；建议下一步 **118**。

