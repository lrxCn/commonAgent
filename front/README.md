# Front（Vue 3 SPA）

演示平台前端：Vue 3 + TypeScript + Vite + Pinia + Naive UI + Vue Router。浏览器只请求 **Back**（`withCredentials` + dev proxy），不直连 Agent。

## 启动顺序

1. **Agent**（内网 Gateway，`18080`）
2. **Back**（迁移 + 种子 + `8080`，CORS 放行 `5173`）
3. **Front**（本目录）

```bash
# 终端 1 — Agent
cd agent && uv sync && uv run uvicorn src.main:app --host 127.0.0.1 --port 18080

# 终端 2 — Back
cd back && uv sync && uv run alembic upgrade head && uv run python -m db.seed
uv run uvicorn src.main:app --host 127.0.0.1 --port 8080

# 终端 3 — Front
cd front && npm install && npm run dev
# http://127.0.0.1:5173
```

生产构建：

```bash
cd front && npm run build
# 产物在 front/dist/
```

## 目录

```text
front/src/
├── api/          # auth, students, admin, kb, chat
├── stores/       # auth.ts, chat.ts
├── views/        # 路由页面
├── components/   # AppLayout, ChatFab, ChatDrawer
├── router/
├── types/
└── main.ts
```

演示脚本：[docs/demo-walkthrough.md](../docs/demo-walkthrough.md) · 路由与数据流：[docs/maps/demo-platform.md](../docs/maps/demo-platform.md)
