# 22 - Back 占位服务

## 依赖

05, 18

## 目标

`back/` 最小服务：模拟登录后转发 Agent；计算并注入 `user_id`、`role_id`、过滤后的 `tools[]`。

## 范围

- Node/Python 任选（建议与团队栈一致；默认 **Python FastAPI** 与 agent 一致）
- `POST /api/chat` → 转发 `POST {AGENT_URL}/internal/chat`
- 硬编码或 `.env` 演示用户：`user_id=demo`, `role_id=demo`, tools 列表来自 `back/config/tools.demo.json`
- **不**实现 JWT（后期 todo）

## 非范围

- 工具执行结果回灌 Agent
- 真实 role 表

## 实现要点

- 鉴权占位：Header `X-Internal-Key` 可选
- 文档说明：真正鉴权在 back，agent 仅内网

## 测试方案

```bash
cd back
# 依实现
uv run pytest tests/test_back_forward.py -v || npm test
# agent 需已启动或 mock
curl -X POST http://127.0.0.1:8080/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"thread_id":"t1","message":"hello"}'
```

期望：200 且 body 来自 agent（或 mock）。

## 完成标准

- README 说明启动顺序：agent → back
- 转发携带完整 context

## 进度更新

`docs/progress.md` **22** → `✅`
