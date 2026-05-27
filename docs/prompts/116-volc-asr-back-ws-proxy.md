# 116 - 火山 SAUC：Back WebSocket 代理与会话

## 建议执行模型

- 模型：GPT-5 或同档强编码模型
- Reasoning：high
- 原因：双 WebSocket 桥接、Session 鉴权、单用户单会话与上游生命周期需与通话信令模式一致且避免资源泄漏。

## 新窗口执行规则

1. 先读 `AGENTS.md`、`README.md`、`docs/progress.md` 与本任务卡。
2. 阅读 PRD：[volcengine-streaming-asr.md](../prd/volcengine-streaming-asr.md)「Front ↔ Back 信令」「架构与边界」。
3. 核对 **115** 已完成。
4. 只实现 Back `WS /api/asr/ws` + 路由注册 + 集成测试；不改 Front（**117**）。
5. 测试通过后更新 `docs/progress.md` **116** → `✅`。
6. 自动 git commit；不 push。

## 依赖

115

## 背景

浏览器经 Cookie Session 连接 Back，由 Back 持有火山凭证并代理 PCM 流。一期信令与 `/api/calls/ws` 分离，避免与 WebRTC 信令耦合。

## 目标

- `WS /api/asr/ws`：未登录关闭连接（与通话 WS 一致风格）。
- 消息契约（JSON 文本 + 二进制音频帧）：

| type | 方向 | 说明 |
|------|------|------|
| `asr.start` | C→S | 开始；`scene: "call"`；`track: "local" \| "remote"`；可选 `call_id` |
| `asr.audio` | C→S | 二进制 PCM 帧（推荐独立 WS binary frame） |
| `asr.stop` | C→S | 结束采集，发上游尾包 |
| `asr.partial` | S→C | 中间转写 |
| `asr.final` | S→C | 稳定句/段 |
| `asr.error` | S→C | `{ code, message }` |
| `asr.ended` | S→C | 上游 `is_last_package` 或正常结束 |

- 每个已登录用户同时仅一个活跃 ASR 上游会话；新 `asr.start` 关闭旧会话（或拒绝并 `asr.error`，在实现中二选一并写进 README）。
- `user.uid` 写入上游 JSON 时使用 Session 的 `user_id`，忽略客户端自报 uid。

## 范围

| 模块 | 变更 |
|------|------|
| `back/src/api/asr_routes.py` | WebSocket 端点 |
| `back/src/services/asr_proxy.py`（或 `volc_asr/session.py`） | 浏览器 WS ↔ `VolcAsrClient` 桥接 |
| `back/src/api/app.py` | `include_router` |
| `back/tests/test_asr_ws.py` | mock 上游 + 双端消息流 |
| `README.md` | Back API 增加 `WS /api/asr/ws`（实现后标为当前事实） |

## 实施步骤

1. 实现 `AsrSessionManager`（进程内单例，与 `CallSignalingHub` 类似）：
   - 注册浏览器 WS；`asr.start` 时创建 `VolcAsrClient` 并 `send_full_request`。
   - 收到 binary / `asr.audio`：转发 PCM 到上游（可按 `VOLC_ASR_SEGMENT_MS` 缓冲）。
   - `asr.stop`：发最后一包音频标记并等待 `is_last_package`。
   - 上游响应 → 解析 utterance/result → 推送 `asr.partial` / `asr.final`；结束推送 `asr.ended`。
   - 上游/本地异常 → `asr.error` 并清理。
2. 凭证缺失（`VOLC_ASR_ACCESS_KEY` / `VOLC_ASR_APP_KEY`）：`asr.start` 后立即 `asr.error` 并关闭，日志不打印完整 key。
3. 注册路由：`/api/asr/ws`；Vite 代理需 `ws: true`（**117** 会用到，本任务可在 README 注明）。
4. `test_asr_ws.py`：登录 fixture + `TestClient` websocket；mock `VolcAsrClient` 或 mock aiohttp 验证 `start` → 2×audio → `stop` → `partial`/`final`/`ended`。
5. README：Back API 列表增加 ASR WS 与消息类型表（链到 PRD）。

## 验证方案

```bash
cd back && uv run pytest tests/test_asr_ws.py -v
cd back && uv run pytest tests/ -q --ignore=tests/test_asr_ws.py  # 回归，可选
```

## 非范围

- Front 麦克风、重采样、UI（**117**）
- 通话中从 `MediaStream` 分支采集（PRD 二期）
- 多 worker / Redis 会话（单进程内存，与通话一致）
- `POST /api/chat` 自动发送 final 文本
- demo-walkthrough B6（**118**）

## 完成标准

- [ ] 未登录 WS 被拒绝。
- [ ] 已登录：`asr.start` → 音频帧 → `asr.stop` → 至少一条 `asr.final` 或 `asr.partial` + `asr.ended`（mock 上游）。
- [ ] Session `user_id` 进入上游 `user.uid`（测试断言 mock 调用参数）。
- [ ] README 已记录 `/api/asr/ws` 与消息类型。
- [ ] progress **116** → `✅`。
- [ ] git commit。

## 进度更新

`docs/progress.md` **116** → `✅`；建议下一步 **117**。

