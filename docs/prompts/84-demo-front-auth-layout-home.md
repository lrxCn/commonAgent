# 84 - 演示平台 Phase 0d：Front 登录、布局、欢迎页与 Chat 空壳

## 建议执行模型

- 模型：GPT-5 或同档强编码模型
- Reasoning：medium
- 原因：路由守卫、Pinia auth、Naive 布局与全局 FAB/Drawer 空壳需一次做对，供后续业务页复用。

## 新窗口执行规则

1. 先读 PRD 模块一（登录、欢迎页、全局对话抽屉、菜单表）。
2. 核对 **82**、**83** 已完成。
3. ChatDrawer 本任务可为空壳（无 SSE）。

## 依赖

82, 83

## 背景

登录后 landing 为 **`/app/home` 欢迎页**（问候 + 用户名 + 角色标签），第一屏是可用应用而非营销页。对话通过右下角 **FAB → 右侧 ~420px drawer**，无独立「对话」菜单。

## 目标

- `LoginView`：`/login`；401 全局跳转登录。
- `AppLayout`：`n-layout` + 侧边栏 + 顶栏（用户名、退出）。
- 侧边栏菜单（一期）：首页、学生管理；admin 菜单占位或隐藏至 **86**。
- `HomeView`：`/app/home` 展示 `/api/me` 信息。
- 路由守卫：`requiresAuth`；`requiresAdmin` 预留。
- `ChatFab.vue` + `ChatDrawer.vue` 空壳（可打开/关闭，无消息流）。
- Pinia `auth` store；`chat` store 仅存 drawer 开闭状态。

## 范围

| 模块 | 变更 |
|------|------|
| `front/src/views/` | Login, Home |
| `front/src/components/layout/` | AppLayout, AppSidebar |
| `front/src/components/chat/` | ChatFab, ChatDrawer（空壳） |
| `front/src/stores/auth.ts` | login/logout/fetchMe |
| `front/src/router/` | 路由表与守卫 |

## 验证方案

```bash
cd front && npm run build
# 手动：Back+Front dev → admin 登录 → 欢迎页见角色标签 → FAB 打开空抽屉
```

## 非范围

- 学生/账号/RAG 业务页（**85–86**、**90**）
- SSE 对话（**91**）
- 删旧 static front（**92**）

## 完成标准

- [ ] 未登录访问 `/app/*` 重定向 `/login`。
- [ ] admin 登录后进欢迎页，顶栏可退出。
- [ ] 任意 `/app/*` 可见 FAB，抽屉宽约 420px。
- [ ] progress **84** → `✅`。

## 进度更新

完成后建议下一步 **85**（MVP 学生 CRUD）。
