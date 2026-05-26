# 92 - 演示平台 Phase 4b：文档收口、legacy Front 移除与演示手册

## 建议执行模型

- 模型：GPT-5 或同档强编码模型
- Reasoning：medium
- 原因：需核对 81–91 实际落地状态，同步 README、maps、PRD 与 progress，避免把计划写成事实。

## 新窗口执行规则

1. 先读 `AGENTS.md`、当前 `README.md`、`docs/progress.md` 与本任务卡。
2. 阅读 PRD：[demo-admin-console.md](../prd/demo-admin-console.md)。
3. 核对任务 **81–91** 均已完成；否则停止。
4. **只做文档与 legacy 清理**，不新增业务功能。
5. 测试以文档核对 + 关键 smoke 为主。

## 依赖

81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91

## 背景

演示平台改变运行时契约：`role_id` → **`role_ids[]`**、Back 库 `common_agent_back`、Vue3 Front 形态。本任务为演示平台批次的 **最终对齐**，与历史 48/57/62/68/74/80 模式一致。

## 目标

- **README.md**：`role_ids[]` context 示例；Back `DATABASE_URL`；演示启动顺序（Agent → Back → `cd front && npm run dev`）；Front 技术栈；边界不变（浏览器不直连 Agent）。
- **docs/demo-walkthrough.md**（新建）：脚本 A/B 逐步操作。
- **docs/maps/**：按需更新 `rag-flow.md`（多 role OR）、新增或更新 `demo-platform.md`（Back/Front 路由与数据流）。
- **docs/prd/demo-admin-console.md**：补充「落地状态 / 偏差」小节。
- **front/**：删除或移除 deprecated 的 `index.html` + `app.js` 静态占位（PRD Phase 4）。
- **docs/progress.md**：81–92 全部 `✅`；总任务数 92；建议下一步回到产品规划。

## 范围

| 模块 | 变更 |
|------|------|
| `README.md` | 契约与演示说明 |
| `docs/demo-walkthrough.md` | 新建 |
| `docs/maps/*.md` | 演示与 RAG OR |
| `docs/prd/demo-admin-console.md` | 落地状态 |
| `docs/progress.md` | 总览、changelog |
| `front/` | 移除 legacy static |

## 验证方案

```bash
rg -n "role_ids" README.md back agent/src
rg -n "common_agent_back|5173" README.md back/.env.example
test ! -f front/app.js || test ! -f front/index.html
# 若 legacy 已删，第二条通过
cd back && uv run pytest tests/ -v --ignore=tests/integration 2>/dev/null | tail -5
cd agent && uv run pytest tests/test_schemas.py tests/test_rag_retrieval.py -v
cd front && npm run build
```

## 非范围

- 新功能、OAuth、PDF 上传（PRD 二期）。
- 修改 `AGENTS.md` 治理顺序（除非用户明确要求）。

## 完成标准

- [ ] README 仅描述已落地事实；无「未实现却写死」的旧 `role_id` 单字段为主契约。
- [ ] demo-walkthrough 可支撑 5min/10min 演示。
- [ ] legacy static front 已移除或明确标记删除并不可作为入口。
- [ ] PRD 有落地状态与已知偏差。
- [ ] progress **92** → `✅`；演示平台 81–92 批次完成。

## 进度更新

`docs/progress.md` **92** → `✅`；总览 92/92 或标注「演示平台批次完成，核心 Agent 80/80 已完成」。
