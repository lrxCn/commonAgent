# 100 - Front：登录页用户名 Enter 聚焦密码

## 建议执行模型

- 模型：GPT-5 或同档强编码模型
- Reasoning：minimal
- 原因：单文件交互微调，无后端变更。

## 新窗口执行规则

1. 先读 PRD §小迭代：登录页用户名回车聚焦密码。
2. 只改 `LoginView.vue`（及必要 ref）。
3. `npm run build` + 手动点击验收；更新 progress 并 commit。

## 依赖

无

## 背景

用户名框 `@keyup.enter="onSubmit"` 会在仅填用户名时触发校验失败 toast，不符合常见「Enter 跳到密码框」习惯。

## 目标

- 用户名 `NInput`：Enter → **`focusPassword()`**（ref 聚焦密码框），**不**提交。
- 密码框：Enter → `onSubmit`（保持）。
- 登录按钮：点击 → `onSubmit`（保持）。

## 范围

| 模块 | 变更 |
|------|------|
| `front/src/views/LoginView.vue` | Enter 行为 |

## 验证方案

```bash
cd front && npm run build
```

手动：

- [ ] 用户名非空、密码为空按 Enter → 焦点在密码框，无错误 toast。
- [ ] 密码框 Enter → 正常登录。
- [ ] 两框均填后点按钮 → 正常登录。

## 非范围

- 自动 focus 用户名（可选，非必须）
- 其他页面键盘行为

## 完成标准

- [ ] 用户名 Enter 仅聚焦密码。
- [ ] progress **100** → `✅`；git commit。

## 进度更新

独立小迭代。
