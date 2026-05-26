# 105 - jumpPage：README、演示手册与文档最终对齐

## 建议执行模型

- 模型：GPT-5 或同档强编码模型
- Reasoning：medium
- 原因：需核对 102–104 实际落地，同步多份文档与契约示例，避免计划写成事实。

## 新窗口执行规则

1. 先读 `AGENTS.md`、当前 `README.md`、`docs/progress.md` 与本任务卡。
2. 阅读 PRD：[jumpPage-client-action.md](../prd/jumpPage-client-action.md)。
3. 核对 **102–104** 均已完成；否则停止。
4. **只做文档与契约对齐**，不新增业务功能。
5. 关键 smoke 测试后更新 progress 并 commit。

## 依赖

102, 103, 104

## 背景

jumpPage 批次（102–104）落地 Back catalog、Agent 对齐与 Front 执行。本任务为该批次 **最终对齐**，模式同历史 92/98/80 等 docs-final 任务。

## 目标

- **README.md**：
  - `client_actions` 示例改为 `page: "students"`（或 `admin-kb`），说明 slug catalog 与 Back enum 关系。
  - 移除或更新 `openTicket` / `pageA` 提及。
  - 演示平台小节注明 jumpPage 已 Front 执行（非仅 console）。
- **docs/demo-walkthrough.md**：B4 改为真实页面话术（admin RAG、alice 学生管理）；删除 openTicket 暗示。
- **docs/maps/client-actions.md**：补充 page registry、slug catalog、Front 执行入口。
- **docs/maps/demo-platform.md**：Chat client_actions 从 stub → router 执行。
- **docs/prd/jumpPage-client-action.md**：补充「落地状态 / 偏差 / 开放问题决议」小节。
- **docs/prd/demo-admin-console.md**：工具白名单示例去掉 openTicket（或标注 superseded by jumpPage PRD）。
- **docs/progress.md**：102–105 全部 `✅`；总任务 105；changelog 记录 jumpPage 批次收口。

## 范围

| 模块 | 变更 |
|------|------|
| `README.md` | client_actions 示例与演示说明 |
| `docs/demo-walkthrough.md` | B4 脚本 |
| `docs/maps/client-actions.md`、`demo-platform.md` | 导航地图 |
| `docs/prd/jumpPage-client-action.md`、`demo-admin-console.md` | 落地状态 |
| `docs/progress.md` | 总览、102–105、changelog |

## 验证方案

```bash
rg -n "pageA|openTicket" README.md docs/
rg -n "jumpPage|page-registry|client-actions/page" README.md front/src docs/maps/
cd back && uv run pytest tests/test_demo_chat_context.py -v
cd agent && uv run pytest tests/test_executor_router.py tests/test_client_actions.py -v
cd front && npm run build
```

## 非范围

- 新功能、catalog 单源 JSON 生成器（PRD 开放问题，二期）
- 修改 `AGENTS.md` 治理顺序（除非用户明确要求）

## 完成标准

- [ ] README 仅描述已落地事实；无 openTicket / pageA 作为当前演示契约。
- [ ] demo-walkthrough B4 可手工走通 jumpPage。
- [ ] PRD 有落地状态与已知偏差。
- [ ] progress **105** → `✅`；jumpPage 批次（102–105）完成。
- [ ] git commit。

## 进度更新

`docs/progress.md` **105** → `✅`；建议下一步：按 [demo-walkthrough.md](../demo-walkthrough.md) 做端到端验收。
