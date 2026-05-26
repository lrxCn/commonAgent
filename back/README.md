# Back（占位网关）

对外 HTTP 层：模拟登录后注入 `user_id`、`role_id`、按角色过滤的 `tools[]`，并转发至内网 **Agent Gateway**。

**安全边界**：真正鉴权在 Back；Agent 仅内网可达，浏览器不直连 Agent。第一期无 JWT，使用 `.env` 演示用户；可选 `INTERNAL_API_KEY` 在转发时带 `X-Internal-Key`（Agent 第一期不校验）。

**用户长期记忆**：由 Agent 内 mem0 + Qdrant 按 `user_id` 维护（Back 不读写）。计划中的 [mem0 All-in（infer=True）](../docs/prompts/24-allin-mem0.md) 在 Agent 侧落地后，同一 `user_id` 跨 thread 偏好由 mem0 去重写入；本地联调若见重复记忆，可按任务卡清空 `QDRANT_COLLECTION_MEM0` 后重试。

## 数据库（演示平台）

Back 业务数据使用 Postgres 库 **`common_agent_back`**（与 Agent 的 `common_agent` **同实例、不同库**）。

```bash
# 创建库（示例；与 Agent 共用同一 Postgres 实例与账号）
createdb common_agent_back

cd back
cp .env.example .env   # 配置 AGENT_DATABASE_URL（与 agent/.env 相同账号，仅库名不同）
uv sync
uv run alembic upgrade head
uv run python -m db.seed
```

`AGENT_DATABASE_URL` 应与 `agent/.env` 的 `DATABASE_URL` 一致（指向 `common_agent`）；Back 会自动推导 `common_agent_back` 连接串。也可直接设置 `DATABASE_URL` 覆盖。

环境变量见 [`.env.example`](.env.example) 中的 `AGENT_DATABASE_URL` / `DATABASE_URL`、`ADMIN_SEED_PASSWORD`。完整演示 walkthrough 见任务 **92**。

## 启动顺序

1. **先启动 Agent**（内网 Gateway）  
2. **再启动 Back**（本服务）

```bash
# 终端 1 — Agent
cd agent
cp .env.example .env   # 按需填写密钥
uv sync
uv run uvicorn main:app --host 127.0.0.1 --port 18080

# 终端 2 — Back
cd back
cp .env.example .env
uv sync
uv run uvicorn main:app --host 127.0.0.1 --port 8080
```

`PYTHONPATH` 由 `uv run` / `pyproject.toml` 的 `pythonpath` 提供（`src`）。

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 存活检查 |
| POST | `/api/chat` | Body: `{ "thread_id", "message" }` → 转发 `POST {AGENT_URL}/internal/chat`，附带完整 `context` |

演示用户（默认）：`user_id=demo`，`role_id=demo`，工具列表见 [`config/tools.demo.json`](config/tools.demo.json)。

**CORS**：允许 `http://127.0.0.1:3000` / `localhost:3000`（Front 静态页），浏览器不直连 Agent。

## 配置

见 [`.env.example`](.env.example)：

- `AGENT_URL` — Agent 基址，默认 `http://127.0.0.1:18080`
- `BACK_PORT` — 本服务端口，默认 `8080`
- `DEMO_*` — 演示身份与工具文件路径
- `DATABASE_URL` — Back 业务库（默认由 `AGENT_DATABASE_URL` 推导为 `common_agent_back`）
- `AGENT_DATABASE_URL` — 与 `agent/.env` 的 `DATABASE_URL` 相同（推荐）
- `ADMIN_SEED_PASSWORD` — 种子 `admin` 密码（默认 `123456`，仅演示）

## 测试

```bash
cd back
uv sync
uv run pytest tests/ -v
```

数据库迁移与种子：`tests/test_demo_database.py`（默认 SQLite fixture；本地 Postgres 集成可选）。

手动（需 Agent 已启动或使用 mock）：

```bash
curl -X POST http://127.0.0.1:8080/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"thread_id":"t1","message":"hello"}'
```

期望：`200`，响应体为 Agent 返回的 SSE 或 JSON（含 `client_actions` 时）。

## 非范围（第一期）

- JWT / 真实用户表
- 工具执行结果回灌 Agent

任务卡：[22-back-stub](../docs/prompts/22-back-stub.md) · Agent mem0 演进：[24-allin-mem0](../docs/prompts/24-allin-mem0.md)
