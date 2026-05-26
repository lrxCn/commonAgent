# Front（Vue 3 SPA）

演示平台前端：Vue 3 + TypeScript + Vite + Pinia + Naive UI + Vue Router。浏览器只请求 **Back**（`withCredentials` + dev proxy），不直连 Agent。

## 启动顺序

1. **Agent**（内网 Gateway）
2. **Back**（CORS 放行 `5173`，见 `back/.env` `CORS_ORIGINS`）
3. **Front**（本目录）

```bash
# 终端 1 — Agent
cd agent && uv sync && uv run uvicorn main:app --host 127.0.0.1 --port 18080

# 终端 2 — Back
cd back && uv sync && uv run uvicorn main:app --host 127.0.0.1 --port 8080

# 终端 3 — Front（Vue SPA）
cd front && npm install && npm run dev
# 浏览器打开 http://127.0.0.1:5173
```

生产构建：

```bash
cd front && npm run build
# 产物在 front/dist/
```

## Legacy 静态占位

任务 **92** 前保留旧静态页文件：

| 文件 | 说明 |
|------|------|
| `legacy.html` | 原占位单页（原 `index.html` 内容） |
| `app.js` | chat / SSE / client_actions |
| `styles.css` | 最小样式 |

本地仍可手动打开 `legacy.html`，或 `npm run start:legacy`（端口 3000）。

## 目录

```text
front/src/
├── api/          # axios 实例（http.ts）
├── stores/       # Pinia
├── views/        # 路由页面
├── components/   # 可复用组件
├── router/
├── types/
└── main.ts
```

任务卡：[83-demo-front-vue-scaffold](../docs/prompts/83-demo-front-vue-scaffold.md)
