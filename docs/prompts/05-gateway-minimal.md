# 05 - Gateway 最小骨架

## 依赖

02, 04

## 目标

FastAPI（或 Starlette）内网 Gateway：`GET /health`、`POST /internal/chat`（先返回 stub）。

## 范围

- `agent/src/gateway/app.py`
- `agent/src/main.py` 入口 `uvicorn`
- 仅监听内网（`0.0.0.0` 可配置，文档标明生产应限内网）
- 请求体用任务 04 的 schema

## 非范围

- 真实图执行、SSE

## 实现要点

- `/internal/chat` 暂返回 `{"status":"stub","thread_id":...}`
- 依赖注入 `get_settings()`

## 测试方案

```bash
cd agent
uv run pytest tests/test_gateway_health.py -v
# 可选：启动后 curl
uv run uvicorn main:app --port 18080 &
sleep 2 && curl -sf http://127.0.0.1:18080/health
```

## 完成标准

- health 200
- chat stub 接受合法 JSON，非法 422

## 进度更新

`docs/progress.md` **05** → `✅`
