# 21 - LangSmith 接入

## 依赖

02, 13

## 目标

全链路 **LangSmith trace**；关键 span 打标签：rewrite、rag_router、retrieve、supervisor、guardrails、rerank。

## 范围

- 环境变量：`LANGCHAIN_TRACING_V2=true`、`LANGCHAIN_API_KEY`、`LANGCHAIN_PROJECT`
- `agent/src/observability/tracing.py`：统一 `traceable` 装饰或 callback
- README：如何在 LangSmith 查看一轮对话

## 非范围

- 看板与 rerank 成本饼图（后期 todo）

## 实现要点

- 不在 trace 中记录完整 secrets；messages 可考虑截断配置
- rerank 节点 metadata：`rerank=true`

## 测试方案

```bash
cd agent
uv run pytest tests/test_tracing.py -v
uv run python -c "
import os
os.environ['LANGCHAIN_TRACING_V2']='false'
from observability.tracing import is_tracing_enabled
assert is_tracing_enabled() in (True, False)
"
```

可选：设置 test project key 跑一条 invoke 并在 LangSmith UI 人工确认（文档说明即可）。

## 完成标准

- tracing 可开关
- 图 invoke 不产生 import 错误

## 进度更新

`docs/progress.md` **21** → `✅`
