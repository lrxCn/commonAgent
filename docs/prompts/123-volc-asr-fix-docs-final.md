# 123 - 火山 SAUC 修复：README、PRD 与 progress 收口

## 建议执行模型

- 模型：较快编码/文档模型即可
- Reasoning：low
- 原因：对照 **119–122** 已实现代码同步契约文档。

## 新窗口执行规则

1. 先读 `README.md`、`docs/progress.md`、handoff、[volcengine-streaming-asr.md](../prd/volcengine-streaming-asr.md) 与本任务卡。
2. 依赖 **119–122** 全部 ✅。
3. 运行 smoke 测试；更新 progress 批次 **119–123** 完成；git commit。

## 依赖

**119**, **120**, **121**, **122**

## 背景

原 **118** 文档宣称 SAUC 批次完成，但 master 存在联调发现的回归；修复批次 **119–123** 完成后需更新 README env 表（新鉴权、2.0 resource）、PRD 落地偏差、handoff 状态。

## 目标

- README：Back `VOLC_ASR_*` 表反映 **X-Api-Key** 语义；resource 1.0/2.0 说明；ASR 协议要点（pcm + audio-only ser=0）；指向 handoff 作历史联调记录。
- PRD `volcengine-streaming-asr.md`：落地状态表增「修复批次 119–123」；信令表含 `asr.track` + binary。
- `volc-asr-fix-handoff.md`：文首标记「已由 119–123 实现」。
- progress：总任务 **123**、批次 **119–123** ✅；changelog。

## 范围

| 文档 | 变更 |
|------|------|
| `README.md` | env、ASR 边界、当前状态 |
| `docs/prd/volcengine-streaming-asr.md` | 落地状态 |
| `docs/prd/volc-asr-fix-handoff.md` | 实现状态 |
| `docs/progress.md` | 119–123、总览 |

非必须：`docs/maps/demo-platform.md` 若与 README 重复则最小更新。

## 验证方案

```bash
cd back && uv run pytest tests/test_volc_asr_protocol.py tests/test_asr_ws.py -v
cd front && npm run build
```

## 非范围

- 新功能（Chat 语音、持久化 transcript）
- 重写 demo Python

## 完成标准

- [ ] README/PRD/progress 与代码一致。
- [ ] smoke 绿。
- [ ] progress **123** ✅；修复批次收口；git commit。

## 进度更新

修复批次 **119–123** 全部 ✅；建议下一步见 progress 总览（如 demo B6 回归或 buglist）。
