# 68 - 结构化记忆写入 Phase 5：README、代码地图与文档最终对齐

## 建议执行模型

- 模型：GPT-5.4
- Reasoning：medium
- 原因：文档收口任务，需核对 63-67 落地代码与 README 当前契约、PRD、maps、progress 一致。

## 新窗口执行规则

1. 先读根目录 `AGENTS.md`、`README.md`、`docs/progress.md` 和本任务卡。
2. 阅读 PRD：[agent-structured-memory-write.md](../prd/agent-structured-memory-write.md)。
3. 核对任务 67 是否完成。
4. 只实现本任务范围；验证通过后更新 progress。

## 依赖

67

## 背景

任务 63-67 完成后，记忆写入应从「统一 infer」变为「fact_update structured + 其他 inferred」双轨。根据根目录 `AGENTS.md`，架构与 memory 语义变化必须同步 README 与 maps。

## 目标

- README 描述双轨写入、Single Extraction Point、`StructuredMemoryRecord` 与 post_turn 路由当前事实。
- 更新 `docs/maps/chat-turn-pipeline.md`、`docs/maps/failure-modes.md`；如需要，更新 `docs/maps/control-plane.md`。
- PRD [agent-structured-memory-write.md](../prd/agent-structured-memory-write.md) 补充落地状态与偏差说明。
- `docs/progress.md` 标记 63-68 收口。
- 可选：更新 [issue/mem0事实抽取失败.md](../../issue/mem0事实抽取失败.md) 关联已落地方案（不删用户原文）。

## 范围

| 模块 | 变更 |
|------|------|
| `README.md` | memory 写入契约、fact_update 路径、mermaid/列表 |
| `docs/maps/chat-turn-pipeline.md` | post_turn 双轨、memory_write_record |
| `docs/maps/failure-modes.md` | stored_empty structured 路径说明 |
| `docs/maps/control-plane.md` | 如需要，Policy → record → store 链路 |
| `docs/prd/agent-structured-memory-write.md` | 落地状态与偏差 |
| `docs/progress.md` | 任务 63-68 最终状态 |
| `issue/mem0事实抽取失败.md` | 可选：增加「已规划/已落地」引用 |

## 文档原则

- README 只写当前已落地事实。
- PRD 保留设计意图；落地状态单独章节。
- maps 不引入 README 未声明的新契约。
- 不改变根 `AGENTS.md` 治理顺序。

## 验证方案

```bash
rg -n "StructuredMemoryRecord|structured.*write|infer=False|Single Extraction|memory_write_record|双轨" README.md docs/maps docs/prd docs/progress.md
rg -n "infer=True.*fact_update|stored_empty" README.md docs/maps
rg -n "TODO|待补|尚未落地" README.md docs/maps docs/progress.md
```

## 非范围

- 不新增运行时功能。
- 不改业务代码，除非文档引用的路径已不存在且必须修正链接。
- 不删除历史 PRD。

## 完成标准

- [ ] README 描述 structured vs inferred 写入当前事实。
- [ ] maps 指向正确实现与测试入口。
- [ ] PRD 落地状态与 README 一致。
- [ ] progress 63-68 与 changelog 完整。
- [ ] 文档治理顺序与 AGENTS.md 一致。

## 进度更新

`docs/progress.md` **68** → 实现完成后改为 `✅`。
