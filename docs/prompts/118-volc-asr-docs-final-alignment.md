# 118 - 火山 SAUC：README、演示手册与文档收口

## 建议执行模型

- 模型：较快编码/文档模型即可
- Reasoning：low
- 原因：对照已实现代码同步契约文档，无复杂逻辑。

## 新窗口执行规则

1. 先读 `AGENTS.md`、`README.md`、`docs/progress.md` 与本任务卡。
2. 核对 **115–117** 均已完成。
3. 只更新文档与 PRD 落地状态；不改运行时逻辑，除非发现文档与代码明显不一致的小修正。
4. 运行文档中引用的 smoke 测试命令。
5. 更新 progress **118** → `✅`；火山 SAUC 批次标记完成。
6. 自动 git commit；不 push。

## 依赖

115, 116, 117

## 背景

PRD [volcengine-streaming-asr.md](../prd/volcengine-streaming-asr.md) 要求实现后同步 README、maps、demo-walkthrough、progress 与 Settings/env 契约。本任务收口 **115–118** 批次。

## 目标

- README：ASR 模块边界（Front→Back→火山；Agent 不参与）、`WS /api/asr/ws`、Back `VOLC_ASR_*` 环境变量表、Front 无密钥说明。
- `docs/maps/demo-platform.md`：ASR 序列图或数据流段落。
- `docs/demo-walkthrough.md`：新增 **B6**（或下一可用编号）语音转写演示步骤。
- PRD `volcengine-streaming-asr.md`：补充「落地状态」与开放问题决议（CallsView 优先、console transcript、不自动 chat 等）。
- `docs/progress.md`：批次 **115–118** 全部 `✅`；总览指标更新。

## 范围

| 文档 | 变更 |
|------|------|
| `README.md` | 当前状态表、Back API、Front 能力、环境变量 |
| `docs/maps/demo-platform.md` | ASR 路由与 WS |
| `docs/demo-walkthrough.md` | B6 脚本 |
| `docs/prd/volcengine-streaming-asr.md` | 落地状态、文档清单勾选 |
| `docs/progress.md` | 118 完成、changelog |

## 实施步骤

1. 通读 `back/src/services/volc_asr/`、`asr_routes`、`front/src/stores/asr.ts`、`ChatDrawer` 实际行为，摘录准确契约。
2. 更新 README「当前状态」：通话页流式 ASR 字幕 ✅；移除「计划」占位（若 **115–117** 已标实现）。
3. demo-walkthrough **B6**：双浏览器 CallsView 通话 → 实时字幕 → 挂断 → 控制台分角色 transcript。
4. demo-platform map：ASR 与 call WS 并列示意。
5. PRD 文末增加「落地状态」表（任务 ID、完成日期、已知偏差）。
6. progress：总任务数 118、已完成 118、建议下一步改为 buglist/backlog。

## 验证方案

```bash
cd back && uv run pytest tests/test_volc_asr_protocol.py tests/test_asr_ws.py -v
cd front && npm run build
```

## 非范围

- 新功能（通话字幕、自动 chat、多 worker）
- 修改 `back/demo/sauc_python` 行为

## 完成标准

- [ ] README / demo-walkthrough / maps / PRD 与代码一致。
- [ ] PRD 文档变更清单项已勾选或注明偏差。
- [ ] progress **115–118** 均为 `✅`；changelog 有记录。
- [ ] git commit。

## 进度更新

`docs/progress.md` **118** → `✅`；火山 SAUC 批次收口；建议下一步见 progress 总览（如 B6 回归或 buglist）。

