# 83 - 演示平台 Phase 0c：Front Vue3 SPA 脚手架

## 建议执行模型

- 模型：GPT-5 或同档强编码模型
- Reasoning：medium
- 原因：需初始化 Vite + Vue3 + TS strict + Pinia + Naive UI + Router，并与 Back 代理/CORS 对齐。

## 新窗口执行规则

1. 先读 `AGENTS.md`、`README.md`、`docs/progress.md`、PRD Front 技术栈与目录建议。
2. 本任务不删除旧 `front/index.html`（留 **92**）。
3. 核对无硬依赖 Back 业务 API（仅需 dev proxy 指向 `:8080`）。

## 依赖

无（可与 81–82 并行）

## 背景

将 `front/` 演进为 Vue 3 SPA。旧静态页在 Phase 4（**92**）删除；本任务只搭脚手架与最小入口。

## 目标

- `front/package.json`：`vue`、`vue-router`、`pinia`、`naive-ui`、`axios`、`typescript`、`vite`。
- `front/tsconfig` strict；`front/vite.config` dev server 默认 **5173**，`proxy` → Back `8080`。
- 目录骨架：`src/api/`、`stores/`、`views/`、`components/`、`router/`、`types/`、`main.ts`。
- 根组件可渲染占位；**不**要求完整业务页。

## 范围

| 模块 | 变更 |
|------|------|
| `front/` | 新 SPA 工程文件 |
| 根 README | 可选一行「演示 Front 开发命令」（详细留 92） |

## 实施步骤

1. 在 `front/` 内 `npm create` 或手工对齐现有 monorepo 习惯。
2. 配置 `axios` 实例：`baseURL` 空（走 proxy）、`withCredentials: true`。
3. 全局注册 Naive UI（按需或全量，与团队习惯一致）。
4. 保留旧 `index.html`/`app.js`，新入口如 `index.html` 指向 Vite（或 `front/demo-app/` 若需并存——优先单入口，旧文件暂 rename 为 `legacy.*` 仅在必要时）。

## 验证方案

```bash
cd front && npm install && npm run build
cd front && npm run dev
# 期望：5173 可打开占位页；无 TS 编译错误
```

## 非范围

- 登录页、Layout、ChatDrawer（**84**、**91**）
- 删除 legacy static（**92**）

## 完成标准

- [ ] `npm run build` 成功。
- [ ] dev proxy 配置存在且指向 Back。
- [ ] progress **83** → `✅`。

## 进度更新

完成后建议下一步 **84**（依赖 82+83 做完整认证 UI）。
