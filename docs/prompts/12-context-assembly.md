# 12 - 上下文组装（K+M+summary 拆开放）

## 依赖

07, 08, 11

## 目标

按 PRD 组装 **system** 与 **messages**：默认 K=4、M=20；summary 覆盖 `[K+1, N-M]` 且不重叠。

## 范围

- `agent/src/memory/assembly.py`：
  - `build_context(mem0, summary, rag_chunks, instructions, messages, k=4, m=20) -> (system_str, lc_messages)`
- 校验 prefix / summary 区间 / recent **无重复**
- 本轮 human 使用 rewrite 后文本（若与原文不同可并存 metadata）

## 非范围

- Supervisor 调用 LLM

## 实现要点

- system：指令 + mem0 + summary + RAG 片段（带 doc/chunk 标签）
- messages：前 K 轮 + 近 M 轮 + 当前 human

## 测试方案

```bash
cd agent
uv run pytest tests/test_context_assembly.py -v
```

构造 N=30 条假消息：断言 system 含 RAG；messages 条数；中间段不在 messages 重复出现。

## 完成标准

- 单测覆盖边界 N < K+M
- 与 architecture §4、§5 一致

## 进度更新

`docs/progress.md` **12** → `✅`
