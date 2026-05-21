# 36 - 上下文预算控制

## 依赖

29, 35

## 背景

trace 显示 system prompt 和消息可能膨胀。需要对 mem0、summary、recent messages、RAG chunks、tools 描述做显式预算。

## 目标

- 所有进入主模型的上下文都有上限。
- 超预算时有稳定裁剪顺序。
- LangSmith metadata 能看出预算使用情况。

## 范围

| 模块 | 变更 |
|------|------|
| `agent/src/settings/config.py` | 新增上下文预算配置 |
| `agent/src/memory/assembly.py` | 实施预算和裁剪顺序 |
| `agent/src/graph/supervisor.py` | tools schema 压缩/限制 |
| `agent/src/observability/tracing.py` | 输出预算 metadata |
| `agent/tests/` | 覆盖超长 mem0/RAG/tools/recent |
| `README.md` | 同步上下文预算 |
| `docs/progress.md` | 本任务状态 |

## 建议预算项

```text
MEMORY_PROFILE_MAX_FACTS
MEM0_FREE_TEXT_MAX_FACTS
SUMMARY_MAX_CHARS
RAG_CHUNK_MAX_CHARS
RAG_CONTEXT_MAX_CHARS
TOOLS_SCHEMA_MAX_CHARS
MODEL_MESSAGE_MAX_TURNS / MAX_CHARS
```

## 非范围

- 不实现 token 精确计数，字符/估算 token 可接受。
- 不改 RAG 检索逻辑。
- 不改 deepagents 触发逻辑。

## 测试方案

```bash
cd agent
uv run pytest tests/test_context_assembly.py tests/test_supervisor.py tests/test_tracing.py -v
```

## 完成标准

- [ ] 超预算输入不会让 system prompt 无限制增长。
- [ ] 裁剪顺序稳定可测。
- [ ] metadata 包含 `system_prompt_len`、`mem0_count`、`rag_chunk_count`、`budget_truncated`。
- [ ] README 与 `docs/progress.md` 同步。

## 进度更新

`docs/progress.md` **36** → 实现完成后改为 `✅`。

