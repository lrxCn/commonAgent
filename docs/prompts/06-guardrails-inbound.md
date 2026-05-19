# 06 - 入站护栏

## 依赖

02, 05

## 目标

对用户 `message` 做入站文本护栏（第一期：规则 + 可选 LangChain/LangSmith 模板钩子）。

## 范围

- `agent/src/guardrails/inbound.py`：`check_inbound(text) -> GuardResult`
- 违规返回可区分原因码（如 `policy_violation`）
- Gateway chat 路由在进图前调用

## 非范围

- 出站、tool 参数护栏

## 实现要点

- 可配置开关 `GUARDRAILS_ENABLED`
- 拦截时 HTTP 400 + 明确 message，**不**写入 checkpoint

## 测试方案

```bash
cd agent
uv run pytest tests/test_guardrails_inbound.py -v
```

用例：正常文本通过；含明显注入样例被拒绝（用固定测试串，不依赖外部 API 时 mock LLM）。

## 完成标准

- Gateway 集成入站检查
- 有单元测试覆盖通过/拒绝

## 进度更新

`docs/progress.md` **06** → `✅`
