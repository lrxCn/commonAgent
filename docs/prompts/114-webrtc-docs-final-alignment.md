# 114 - WebRTC 通话：README、演示脚本与地图收口

## 建议执行模型

- 模型：GPT-5 或同档强编码模型
- Reasoning：low
- 原因：文档对齐与手工验收清单，无复杂逻辑。

## 新窗口执行规则

1. 先读 `AGENTS.md`、`README.md`、`docs/progress.md` 与本任务卡。
2. 阅读 PRD：[webrtc-account-call.md](../prd/webrtc-account-call.md)。
3. 核对 **111–113** 均已完成。
4. 同步文档、PRD 落地状态、progress 总览；不改动信令/RTC 行为除非发现文档与实现不一致的小修正。
5. 按 demo-walkthrough B5 做手工验收记录；commit。

## 依赖

111, 112, 113

## 背景

WebRTC 批次功能已在 111–113 落地。本任务将运行契约写入 README/maps/demo-walkthrough，更新 PRD 落地状态，并把 progress 总任务数收口为 114。

## 目标

- README：Front 路由表含 `/app/calls`；Back API 含 calls；明确 **Agent 不参与**；单进程信令限制；可选 `VITE_WEBRTC_STUN_URL`。
- `docs/maps/demo-platform.md`：路由行 + 信令序列摘要。
- `docs/demo-walkthrough.md`：新增 **B5** 双账号通话脚本（alice↔bob）。
- `docs/prd/webrtc-account-call.md`：落地状态表 ✅；链接任务卡 111–114。
- `docs/progress.md`：批次 111–114 完成；总任务 114；建议下一步改为 B5 验收或 backlog。

## 范围

| 模块 | 变更 |
|------|------|
| `README.md` | 当前状态表、Back/Front 契约、环境变量 |
| `docs/maps/demo-platform.md` | 路由 + 信令 |
| `docs/demo-walkthrough.md` | B5 |
| `docs/prd/webrtc-account-call.md` | 落地状态 |
| `docs/progress.md` | 114 ✅、changelog |

## 实施步骤

1. 对照实现检查 WS 路径、消息 type 名称与 PRD 一致；不一致时以代码为准更新 PRD/README。
2. README「当前状态」增加通话能力一行（已实现）。
3. demo-platform 增加 `/app/calls`、WS `/api/calls/ws`、`GET /api/calls/peers`。
4. demo-walkthrough B5：双浏览器步骤、拒接/接听/挂断检查点。
5. PRD 文末增加「落地状态」表，四项 ✅。
6. progress：总览指标、批次说明、changelog。

## 验证方案

```bash
cd back && uv run pytest tests/test_call_signaling.py -v
cd front && npm run build
rg -n "webrtc|/app/calls|/api/calls" README.md docs/demo-walkthrough.md docs/maps/demo-platform.md
```

手工：完整走一遍 B5。

## 非范围

- 新功能（录像、视频、TURN 运维）
- 修改 `AGENTS.md` 治理
- 自动 Playwright 双浏览器 CI（可记 backlog）

## 完成标准

- [x] README/maps/demo-walkthrough/PRD 与 111–113 实现一致。
- [ ] B5 手工验收通过（双浏览器 alice↔bob，需本地服务运行）。
- [x] progress **114** → `✅`；WebRTC 批次 111–114 全部完成。
- [ ] git commit。

## 进度更新

`docs/progress.md` **114** → `✅`；建议下一步：按 demo-walkthrough **B5** 回归或处理 backlog。
