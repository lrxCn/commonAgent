# 99 - Front：换用户登录后重置 thread_id

## 建议执行模型

- 模型：GPT-5 或同档强编码模型
- Reasoning：medium
- 原因：auth/chat store 协作与 sessionStorage 边界；逻辑清晰但需覆盖登出/刷新场景。

## 新窗口执行规则

1. 先读 PRD [kb-multi-role-rag.md](../prd/kb-multi-role-rag.md) §小迭代：换用户登录后重置 thread_id。
2. 阅读 `front/src/stores/chat.ts`、`front/src/stores/auth.ts`。
3. **不修改** Back/Agent 契约；thread 归属仍以 Back 为准。
4. 手动验收 + `npm run build`；更新 progress 并 commit。

## 依赖

无（可与 93–98 并行）

## 背景

`thread_id` 存在 `sessionStorage`（`common_agent_thread_id`），未与 `user_id` 绑定。同 tab 换账号会复用旧 thread，导致 403 或短暂展示上一用户消息。

## 目标

- sessionStorage 增加 **`common_agent_last_user_id`**（或与 thread 合并为 JSON 对象）。
- 登录成功或 `initialize` 拉到 `/api/me` 后：`chatStore.ensureThreadForUser(user_id)` — 若 `last_user_id !== user_id` 则 `startNewThread()` 并更新 `last_user_id`。
- `logout` / `clearSession`：`chatStore.resetOnLogout()`（abort 流式、清 messages、清除 storage）。
- **同用户**刷新/再开 drawer：保留 thread_id，历史可加载。
- **新开对话**按钮行为不变。

## 范围

| 模块 | 变更 |
|------|------|
| `front/src/stores/chat.ts` | `ensureThreadForUser`、`resetOnLogout` |
| `front/src/stores/auth.ts` | 登录/登出/initialize 挂钩 |

## 验证方案

```bash
cd front && npm run build
```

手动验收：

- [ ] A 对话后登出，B 登录：thread_id 不同，历史为空，首条消息正常。
- [ ] B 登出后 A 再登录：新 thread，看不到 B 的消息。
- [ ] 同用户刷新：thread_id 不变，历史可加载。
- [ ] 「新开对话」仍手动换新 thread。

## 非范围

- Back thread 校验逻辑（已有）
- KB 多角色（93–98）
- README 大改（可在 **98** 或本任务仅 progress 备注）

## 完成标准

- [ ] 换账号不复用旧 thread_id。
- [ ] build 通过；progress **99** → `✅`；git commit。

## 进度更新

独立小迭代；建议与 **100**、**101** 任意顺序执行。
