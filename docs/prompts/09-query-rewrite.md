# 09 - Query Rewrite

## 依赖

07, 08

## 目标

用 **mem0 + 短期记忆**（不用 RAG）将用户问题改写为 `rewritten_query`。

## 范围

- `agent/src/rag/rewrite.py`：`rewrite_query(user_message, mem0_text, recent_messages) -> str`
- 可配置模型名；测试 mock LLM
- 写入 graph state 字段 `rewritten_query`

## 非范围

- RAG 检索本身

## 实现要点

- 遵循 PRD：**rewrite 阶段不读 RAG 结果**
- prompt 模板放 `agent/src/rag/prompts/rewrite.txt` 或内联常量

## 测试方案

```bash
cd agent
uv run pytest tests/test_rewrite.py -v
```

mock：给定「它」+ 短期上下文含「报销流程」，输出应包含「报销」等可断言关键词（或 snapshot）。

## 完成标准

- 纯函数可单测
- 图节点 `rewrite_node` 可调用

## 进度更新

`docs/progress.md` **09** → `✅`
