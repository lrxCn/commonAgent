# 122 - 火山 SAUC 修复：Front 分轨延迟 asr.start

## 建议执行模型

- 模型：较快编码模型即可
- Reasoning：low
- 原因：Pinia store 时序调整，范围在 `asr.ts` 与 CallsView 绑定。

## 新窗口执行规则

1. 先读 handoff §2.4、`front/src/stores/asr.ts`、`stores/call.ts`、本任务卡。
2. 依赖 **121**（Back 清理逻辑就绪）。
3. 不引入 `[ASR-TIMELINE]` debug。
4. `npm run build`；progress **122** ✅；git commit。

## 依赖

**121**

## 背景

日志证实：`in_call` 时立即双轨 `asr.start`，但 `getLocalStream()` 常为 null（`local_stream_missing`），导致 local 轨无 PCM、Back `had_browser_pcm=False` → 45000081；「我说」栏无字幕。

## 目标

- **local**：`getLocalStream()`（或等价 MediaStream）就绪后再 `asr.start` + `startLocalCapture`。
- **remote**：`remoteStream` 就绪后再 `asr.start` + `startRemoteCapture`（与 watch 合并，避免重复 start）。
- 挂断：`asr.stop` 仅对已 start 的 track 发送。
- 双浏览器手工：双方「我说 / 对方说」均能有 partial/final。

## 范围

| 区域 | 变更 |
|------|------|
| `front/src/stores/asr.ts` | 分轨 start/stop 状态机 |
| `front/src/views/CallsView.vue` | 仅当绑定逻辑变化时需要 |

## 实施步骤

1. 拆分 `startCallTracks`：WS 连接可仍全局一次；`asr.start` 按轨触发。
2. watch `callStore` local/remote stream；就绪时 idempotent start。
3. `stopAll` 根据已激活 track 列表 stop。
4. 移除任何实验 A 遗留 debug。

## 验证方案

```bash
cd front && npm run build
```

手工（handoff §5.2）：alice↔bob，**双方各说话**，确认两栏字幕 + 无 45000151。

## 非范围

- Back 协议/鉴权（**119–120**）
- README 收口（**123**）

## 完成标准

- [ ] 不再出现稳定 `local_stream_missing` 且 local 无 PCM。
- [ ] front build 绿。
- [ ] progress **122** ✅；git commit。

## 进度更新

建议下一步 **123**。
