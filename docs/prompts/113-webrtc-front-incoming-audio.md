# 113 - WebRTC 通话：全局来电弹窗与音频全流程

## 建议执行模型

- 模型：GPT-5 或同档强编码模型
- Reasoning：high
- 原因：WebRTC offer/answer/ICE、浏览器媒体权限与全局 WS 生命周期，集成风险高。

## 新窗口执行规则

1. 先读 `AGENTS.md`、`README.md`、`docs/progress.md` 与本任务卡。
2. 阅读 PRD：[webrtc-account-call.md](../prd/webrtc-account-call.md)（来电弹窗、WebRTC、AppLayout）。
3. 核对 **112** 已完成。
4. 完成被叫来电、接听/拒接、音频通话、挂断及资源释放。
5. 测试通过后更新 progress 并 commit。

## 依赖

112

## 背景

112 已具备通话页与主叫信令。本任务补齐：**任意 `/app/*` 页左下角来电**、接听后跳转通话页、caller/callee 双方 `RTCPeerConnection` 音频联通与挂断清理。

## 目标

- `IncomingCallToast.vue`：左下角 fixed；显示 `from_display_name`；**接听** / **拒接**。
- `AppLayout.vue`：挂载 toast；`onMounted` 对已登录用户 `callStore.connectSignaling()`；`logout` 时 `disconnect()`。
- WebRTC：`call.accepted` 后 caller 建 offer → `rtc.offer`；callee 在 **接听按钮** 内 `getUserMedia({ audio: true })` 再 `call.accept` → 收 offer 建 answer。
- Trickle ICE：`rtc.ice` 双向转发。
- 通话页 `in_call`：计时、**挂断**、远端 `<audio autoplay>`（`srcObject`）。
- 拒接/挂断/对方结束：关闭 PC、stop tracks、`phase → idle`。
- 文案：`对方已拒接` / `已取消呼叫` / `对方已挂断`（message 或 store 字段）。

## 范围

| 模块 | 变更 |
|------|------|
| `front/src/components/call/IncomingCallToast.vue` | 来电 UI |
| `front/src/components/layout/AppLayout.vue` | 全局 WS + toast |
| `front/src/stores/call.ts` | PC、media、accept/reject/hangup、rtc 处理 |
| `front/src/views/CallsView.vue` | in_call UI、远端音频 |
| `front/src/stores/auth.ts` | logout 时断开 call（若未在 layout 覆盖） |
| `front/.env.example` | 可选 `VITE_WEBRTC_STUN_URL`、`VITE_CALL_WS_PATH` 注释 |

## 实施步骤

1. 将 `connectSignaling` 从仅 `CallsView` 提升到 `AppLayout`（112 若已写在 CallsView 则迁移）。
2. `call.incoming` → 设置 `incomingCall`；toast 显示。
3. `rejectIncoming()` → `call.reject`；清空 incoming。
4. `acceptIncoming()` → `call.accept` → `router.push({ name: 'app-calls' })`；在 `getUserMedia` 成功后继续。
5. `onCallAccepted`：caller 创建 `RTCPeerConnection`（`iceServers` 用 env 或默认 Google STUN），addTrack，createOffer，setLocalDescription，发 `rtc.offer`。
6. Callee 收 `rtc.offer`：setRemoteDescription，createAnswer，发 `rtc.answer`；双方 `onicecandidate` → `rtc.ice`。
7. `ontrack`：绑定远端流到 audio 元素。
8. `hangup()` → `call.hangup` + 本地 cleanup。
9. 处理 `call.ended`、`call.rejected`、`call.canceled`、`peer disconnected`。
10. 组件测试：`IncomingCallToast` 渲染来电名；可选 store rtc mock。

## 验证方案

```bash
cd front && npm run build
cd front && npm run test -- --run
cd back && uv run pytest tests/test_call_signaling.py -v
```

手工（必做）：

1. 浏览器 A：`alice` → 通话页呼叫 `bob`。
2. 浏览器 B：`bob` 在 `/app/students` → 左下角来电 → **拒接** → A 显示已拒接。
3. 再次呼叫 → **接听** → 双方说话可听 → 任一方 **挂断** → 双方 idle。

## 非范围

- 视频轨、屏幕共享、通话记录
- TURN 部署（仅 STUN；跨网失败记 README 限制）
- README / demo-walkthrough / maps（**114**）
- Agent 集成

## 完成标准

- [ ] 非通话页可收到左下角来电；接听/拒接/挂断符合 PRD。
- [ ] 双浏览器音频通话成功（localhost 或同 LAN）。
- [ ] 挂断后无残留麦克风占用（浏览器指示熄灭）。
- [ ] front build 绿。
- [ ] progress **113** → `✅`。
- [ ] git commit。

## 进度更新

`docs/progress.md` **113** → `✅`；建议下一步 **114**。
