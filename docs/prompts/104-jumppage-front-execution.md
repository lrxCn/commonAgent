# 104 - jumpPage：Front 路由执行与 page registry

## 建议执行模型

- 模型：GPT-5 或同档强编码模型
- Reasoning：medium
- 原因：Pinia + Vue Router + 权限边界，需与现有 auth guard 一致。

## 新窗口执行规则

1. 先读 `AGENTS.md`、`README.md`、`docs/progress.md`、PRD 与本任务卡。
2. 核对 **102**、**103** 已完成。
3. 只实现 Front 执行层；文档大改留 **105**。
4. `npm run build` 通过后更新 progress 并 commit。

## 依赖

102, 103

## 背景

`front/src/stores/chat.ts` 的 `handleClientActions` 仍为 console 占位。PRD 要求 slug → Vue route 映射，未知 slug toast，admin 页与 `router.beforeEach` 行为一致。

## 目标

- 新增 `front/src/client-actions/page-registry.ts`（或 `config/nav-pages.ts`）：
  - `PageSlug` 类型与 PRD 五档 slug 一致。
  - `resolveJumpPageTarget(page: string): RouteLocationRaw | null`
  - `isPageAllowedForUser(page: PageSlug, isAdmin: boolean): boolean`
- `handleClientActions`：`tool === "jumpPage"` → 校验 slug → `requires_approval`（保留 confirm 分支）→ `router.push`。
- 失败 UX：Naive UI `message.warning`（未知 page / 无权限）；**不**静默跳首页。
- 跳转成功后 **默认保持 ChatDrawer 打开**（PRD 开放问题决议；若实现时改关闭须在 commit message 说明）。

## 范围

| 模块 | 变更 |
|------|------|
| `front/src/client-actions/page-registry.ts` | 新建 |
| `front/src/stores/chat.ts` | 执行 jumpPage |
| `front/src/types/index.ts` | 可选 `JumpPageArgs` |
| `front/src/components/chat/ChatDrawer.vue` | 更新占位文案（若仍写 console 演示） |
| 单元测试 | 可选 `page-registry` 纯函数测试（Vitest 若项目已有则加，否则 build + 手动） |

## 实施步骤

1. 实现 registry，slug 映射到 `router/index.ts` 已有 route name。
2. 在 `chat.ts` 注入 `useRouter()` / 从 composable 获取 router（遵循现有 store 模式）。
3. 非 admin 访问 admin-* slug：与 `requiresAdmin` guard 一致（拒绝并提示）。
4. 移除或降级纯 console 日志为 debug 级别（成功跳转仍可在 dev console 留一条 info）。

## 验证方案

```bash
cd front && npm run build
# 手动：
# 1. admin 登录 → 对话「打开 RAG 管理」→ URL 变为 /app/admin/kb
# 2. alice 登录 → 「打开学生管理」→ /app/students
# 3. alice → 「打开用户管理」→ 提示无权限，停留当前页
```

## 非范围

- Back / Agent 改动
- README、demo-walkthrough、maps（**105**）
- query 深链、跳转结果回传 Agent

## 完成标准

- [ ] `jumpPage` client_action 触发真实路由切换。
- [ ] 未知 slug 与无权限有用户可见提示。
- [ ] `npm run build` 绿。
- [ ] progress **104** → `✅`。
- [ ] git commit。

## 进度更新

`docs/progress.md` **104** → `✅`；建议下一步 **105**。
