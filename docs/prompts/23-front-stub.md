# 23 - Front 占位

## 依赖

22

## 目标

`front/` 最小页面：sessionStorage 存 `thread_id`；调 back chat；展示 SSE 流；解析并 **console.log** `client_actions`（执行留后期）。

## 范围

- 单页 HTML+JS 或 Vite 最小项目
- 打开时无 thread_id 则 `crypto.randomUUID()`
- `requires_approval=true` 时 `confirm()` 后再 log
- 历史：按钮拉 `back` 代理的 history API（若 22 已代理）

## 非范围

- 美观 UI、router.push 真实跳转

## 实现要点

- 不直连 agent URL
- 改权限/上传文档提示「请新开 thread」（文案即可，逻辑后期）

## 测试方案

```bash
# 手动
cd front && npx serve . -p 3000
# 浏览器打开，发消息，Network 见 SSE；触发 jumpPage 意图见 console client_actions
```

自动化（可选）：

```bash
cd front && npm run test:e2e  # 若配置了 playwright 冒烟
```

**通过标准**：README 含手动测试步骤；能连 back 完成一轮对话。

## 完成标准

- thread_id 持久化在 sessionStorage
- client_actions 解析不抛错

## 进度更新

`docs/progress.md` **23** → `✅`；总览「已完成」= 23 时可标 **第一期完成**
