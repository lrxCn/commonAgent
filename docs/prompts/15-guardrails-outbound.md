# 15 - 出站护栏

## 依赖

06, 13

## 目标

**整段**生成后再做出站文本护栏（第一期）；违规替换为安全回复或 500+日志。

## 范围

- `agent/src/guardrails/outbound.py`：`check_outbound(text) -> GuardResult`
- 图节点在 Supervisor 之后、写 checkpoint 之前
- 流式：第一期可缓冲全文再检（与 PRD 一致）

## 非范围

- 流式分段检测

## 实现要点

- 与入站共用配置开关
- LangSmith 记录 block 事件

## 测试方案

```bash
cd agent
uv run pytest tests/test_guardrails_outbound.py -v
```

## 完成标准

- 集成到图；mock 违规输出被拦截

## 进度更新

`docs/progress.md` **15** → `✅`
