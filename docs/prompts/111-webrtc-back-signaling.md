# 111 - WebRTC 通话：Back peers API 与 WebSocket 信令

## 建议执行模型

- 模型：GPT-5 或同档强编码模型
- Reasoning：high
- 原因：WebSocket 状态机、Session 鉴权与多连接转发，需处理忙线/离线/角色校验等边界。

## 新窗口执行规则

1. 先读根目录 `AGENTS.md`、`README.md`、`docs/progress.md` 与本任务卡。
2. 阅读 PRD：[webrtc-account-call.md](../prd/webrtc-account-call.md) 全文（Back API 与信令契约）。
3. 核对 **110** 已完成；本任务无其它依赖。
4. 只实现 Back REST + WS + 测试；不改 Front、不改 Agent。
5. 测试通过后更新 `docs/progress.md` **111** → `✅`。
6. 自动 git commit；不 push。

## 依赖

110

## 背景

演示平台需支持账号间 1:1 音频通话。信令经 Back WebSocket 中继，媒体不经 Agent。本任务交付可独立测试的信令层，供 Front **112–113** 对接。

## 目标

- `GET /api/calls/peers`：返回除当前用户外的可呼叫用户列表。
- `WS /api/calls/ws`：Cookie Session 鉴权；内存维护 `user_id → WebSocket` 与 `call_id` 会话；实现 PRD 所列 `call.*` / `rtc.*` 消息转发与校验。
- 单用户新连接踢掉旧连接并推送 `session.replaced`。
- 被叫离线 → `call.failed`（`callee_offline`）；被叫忙线 → `call.busy`。

## 范围

| 模块 | 变更 |
|------|------|
| `back/src/api/call_routes.py` | REST `peers` + WebSocket 端点 |
| `back/src/services/call_signaling.py` | 信令路由表、invite/accept/reject/hangup、SDP/ICE 转发 |
| `back/src/api/app.py` | `include_router(call_router)` |
| `back/tests/test_call_signaling.py` | 双 WS 客户端集成测试 |
| `README.md` | **计划**小节：通话 API/WS 路径（标注未实现→实现后改事实） |

## 实施步骤

1. 新增 `list_call_peers(db, current_user_id)`：查询 `users` 表，排除自己，按 `username` 排序，返回 `user_id/username/display_name`。
2. 实现 `CallSignalingHub`（进程内单例或模块级 dict）：
   - 注册/注销连接；新连接替换旧连接。
   - `call.invite`：校验 `to_user_id` 存在且非自己；若 callee 无连接 → `call.failed`；若 callee 已在 `accepted` 通话 → `call.busy`；生成 `call_id`（UUID），状态 `ringing`。
   - `call.accept` / `call.reject`：仅 callee；`accept` 后状态 `accepted` 并双方 `call.accepted`。
   - `call.cancel`：仅 caller、仅 `ringing`。
   - `call.hangup`：双方均可；清理会话并 `call.ended`。
   - `rtc.offer` / `rtc.answer` / `rtc.ice`：仅该 `call_id` 参与方，转发给对端。
3. WebSocket 握手：无 Session → 关闭（4401 或 403，与现有错误风格一致）；成功推送 `{ "type": "connected", "user_id" }`。
4. 客户端 JSON 解析失败 → `{ "type": "error", ... }`。
5. 注册路由 `prefix=/api/calls`；WS 路径固定为 `/api/calls/ws`（与 PRD 一致）。
6. 编写 `test_call_signaling.py`：登录 fixture 获取 cookie；`TestClient` 或 `httpx`/`websockets` 双连接覆盖 PRD 测试计划 Back 部分。
7. README：在 Back API 列表增加通话条目（实现后去掉「计划」标记——本任务完成即写为**当前事实**）。

## 验证方案

```bash
cd back && uv run pytest tests/test_call_signaling.py -v
cd back && uv run pytest tests/ -q --ignore=tests/test_call_signaling.py  # 回归，可选
```

若本地无 Postgres，peers 测试可用现有 `test_demo_*` 同款 DB fixture（与 `conftest.py` 一致）。

## 非范围

- Front / WebRTC / `getUserMedia`（**112–113**）
- 通话历史数据库表
- TURN 配置、多 worker 部署支持（README 注明单进程内存 hub）
- Agent、`client_actions`
- `docs/demo-walkthrough.md` B5（**114**）

## 完成标准

- [ ] `GET /api/calls/peers` 需登录；响应不含当前用户。
- [ ] WS 信令用例：invite→incoming→reject；invite→accept→offer/answer/ice 转发；离线 failed；忙线 busy。
- [ ] README Back API 已记录 `/api/calls/peers` 与 `WS /api/calls/ws`。
- [ ] progress **111** → `✅`。
- [ ] git commit。

## 进度更新

`docs/progress.md` **111** → `✅`；建议下一步 **112**。
