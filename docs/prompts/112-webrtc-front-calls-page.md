# 112 - WebRTC 通话：Front 信令连接、call store 与通话页

## 建议执行模型

- 模型：GPT-5 或同档强编码模型
- Reasoning：medium
- 原因：Pinia 状态机 + WebSocket 封装 + 新页面，但本任务可不建 PeerConnection（留给 113）。

## 新窗口执行规则

1. 先读 `AGENTS.md`、`README.md`、`docs/progress.md` 与本任务卡。
2. 阅读 PRD：[webrtc-account-call.md](../prd/webrtc-account-call.md)（Front 模块划分、状态机、环境变量）。
3. 核对 **111** 已完成（Back WS 可连）；否则停止。
4. 实现通话页、store、WS 连接与呼叫状态 UI；**本任务不要求音频连通**（113 完成 WebRTC）。
5. 测试通过后更新 progress 并 commit。

## 依赖

111

## 背景

Back 信令已就绪。本任务让 Front 能连 WS、拉取 peers、发起/取消呼叫，并在通话页展示主叫侧状态（`outgoing` / 收到 `rejected` / `canceled`）。被叫来电弹窗与 WebRTC 在 **113**。

## 目标

- `front/src/api/calls.ts`：`fetchPeers()`。
- `front/src/types/call.ts`：信令消息与 store 状态类型。
- `front/src/stores/call.ts`：连接 WS、发送 `call.invite` / `call.cancel` / `call.hangup`、处理服务端事件更新状态（不含 PC）。
- `front/src/composables/useCallSignaling.ts`（或等价）：`ws` URL 由 `window.location` + `VITE_CALL_WS_PATH`（默认 `/api/calls/ws`）构建；断线指数退避重连。
- `CallsView.vue`：用户列表 + 「呼叫」；`outgoing` 时显示「正在呼叫…」+ 取消。
- 路由 `/app/calls`（`app-calls`）、侧边栏「通话」菜单项。
- **不在本任务挂载** `IncomingCallToast`（113）；但 store 应能设置 `incomingCall` 供后续使用。

## 范围

| 模块 | 变更 |
|------|------|
| `front/src/api/calls.ts` | `GET /api/calls/peers` |
| `front/src/types/call.ts` | 类型定义 |
| `front/src/stores/call.ts` | WS + 状态机（idle/outgoing/incoming/in_call 预留） |
| `front/src/composables/useCallSignaling.ts` | WS 生命周期 |
| `front/src/views/CallsView.vue` | 通话页 UI |
| `front/src/router/index.ts` | 路由 |
| `front/src/components/layout/AppSidebar.vue` | 菜单 |
| `front/vite.config.ts` | 确认 `/api` 代理含 WS upgrade（若需则补 `ws: true`） |

## 实施步骤

1. 定义 `CallPhase`: `idle` | `outgoing` | `incoming` | `in_call`；`activeCall` 含 `callId`、`peerUserId`、`peerDisplayName`、`role: 'caller' | 'callee'`。
2. `connectSignaling()`：登录后在 `CallsView` onMounted 调用（113 会移到 `AppLayout`）；cookie 随 WS 发送。
3. 处理事件：`call.ringing`、`call.rejected`、`call.canceled`、`call.failed`、`call.busy`、`call.ended`、`error`、`session.replaced`（toast 提示）。
4. `invitePeer(user)` → `call.invite`；`cancelOutgoing()` → `call.cancel`。
5. `CallsView`：Naive UI 表格/列表，风格对齐 `StudentsView`。
6. 路由与侧边栏注册。
7. Vitest（可选但建议）：store 在 mock WS 下 `idle → outgoing → idle`（reject）。

## 验证方案

```bash
cd back && uv run pytest tests/test_call_signaling.py -v
cd front && npm run build
cd front && npm run test -- --run  # 若新增 store 测试
```

手工（与 111 联调）：

1. `alice` 打开 `/app/calls`，列表含 bob，不含自己。
2. 点呼叫 bob（bob 未开页）→ 显示呼叫中；bob 侧暂无 UI 亦可。
3. 用浏览器 devtools 或临时脚本验证 WS 收到 `call.incoming`（完整 UI 在 113）。

## 非范围

- `RTCPeerConnection`、`getUserMedia`、`<audio>`（**113**）
- `IncomingCallToast`、`AppLayout` 全局 WS（**113**）
- `call.accept` / `call.reject` UI（**113**）
- README / demo-walkthrough 最终稿（**114**）

## 完成标准

- [ ] `/app/calls` 可访问；peers 列表正确。
- [ ] 主叫可 invite、cancel；能处理 rejected/failed/busy 并回到 idle。
- [ ] front build 绿。
- [ ] progress **112** → `✅`。
- [ ] git commit。

## 进度更新

`docs/progress.md` **112** → `✅`；建议下一步 **113**。
