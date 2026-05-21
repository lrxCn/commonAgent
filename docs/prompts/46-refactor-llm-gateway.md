# 46 - 大重构 Phase 5：统一 LLM Gateway 与模型用途策略

## 建议执行模型

- 模型：GPT-5.5
- Reasoning：high
- 原因：会收敛 rewrite/router/chitchat/supervisor/mem0/rerank/embedding 的 provider 调用，涉及成本、超时、流式、trace 和降级路径。

## 依赖

45

## 背景

当前 LLM/Embedding/Rerank 调用分散在多个模块：

- rewrite/router/chitchat 使用各自的 ChatOpenAI 构造和 timeout/max_tokens。
- supervisor/answer executor 单独构造主模型并处理 streaming callback。
- mem0 write 使用专用小模型配置并接管 mem0 内部 client timeout。
- rerank 使用 `urllib` 调 `/rerank`。
- ingest/retriever 分别构造 embedding client。

这让模型策略、trace metadata、timeout 和 fallback 难以统一。

## 目标

- 新增 `infrastructure/llm/`，按 `ModelUseCase` 统一 provider 调用。
- 将 chat、embedding、rerank 的 client 构造集中管理。
- 保持现有环境变量契约，除非确有必要新增；如新增必须同步 `config.py`、`.env.example`、`.env` 和测试。
- 保持现有 streaming、timeout、fallback 行为。

## 范围

| 模块 | 变更 |
|------|------|
| `agent/src/infrastructure/llm/` | 新增 LLM Gateway、model policy、chat/embedding/rerank client |
| `agent/src/contracts/llm.py` 或等价模块 | 定义 `ModelUseCase`、request/response metadata |
| `agent/src/rag/rewrite.py` | 改用 LLM Gateway |
| `agent/src/rag/router.py` | 改用 LLM Gateway |
| `agent/src/graph/chitchat_executor.py` | 改用 LLM Gateway |
| `agent/src/graph/supervisor.py` | 主模型和 streaming callback 接入 LLM Gateway |
| `agent/src/memory/mem0_write.py` / `mem0_client.py` | 保持 mem0 专用模型策略，必要时通过 Gateway 提供配置 |
| `agent/src/rag/ingest.py` / RAG store | embedding 改用 Gateway |
| `agent/src/domain/rag` 或 rerank adapter | rerank 改用 Gateway |
| `agent/tests/` | 覆盖 use case 策略、timeout、fallback、streaming |
| `agent/.env.example`、`agent/.env`、`agent/src/settings/config.py` | 仅在新增/变更环境契约时同步 |
| `README.md` | 同步 LLM 调用边界 |
| `docs/progress.md` | 本任务状态 |

## ModelUseCase 建议

| 用途 | 说明 |
|------|------|
| `MAIN_ANSWER` | deepagents 或普通主回复 |
| `RAG_ANSWER` | 简单 RAG answer executor |
| `REWRITE` | 指代消解 |
| `ROUTER` | 模糊 turn 的 RAG 分类 |
| `CHITCHAT` | 轻量寒暄 |
| `MEM0_WRITE` | mem0 infer 写入 |
| `EMBEDDING` | embedding |
| `RERANK` | rerank |

## 非范围

- 不更换默认模型。
- 不改变 prompt 文案。
- 不改变 turn routing 或 executor routing。
- 不引入新 provider。
- 不改变 `.env` 契约，除非当前配置无法表达必要 use case。

## 环境契约要求

如新增、删除、重命名或改变任何环境变量含义/default：

- 同步 `agent/src/settings/config.py`。
- 同步 `agent/.env.example`。
- 同步本机 `agent/.env`。
- 运行：

```bash
cd agent
uv run pytest tests/test_settings.py -v
```

## 测试方案

```bash
cd agent
uv run pytest tests/test_rewrite.py tests/test_rag_router.py tests/test_chitchat_executor.py tests/test_supervisor.py tests/test_mem0_write.py tests/test_rag_retrieval.py tests/test_kb_ingest.py tests/test_chat_sse.py -v
uv run pytest tests -v
uv run ruff check src tests
```

## 完成标准

- [ ] 业务模块不再直接散落 provider client 构造，或仅保留明确兼容层。
- [ ] 每个 LLM/Embedding/Rerank 调用都有 `ModelUseCase`。
- [ ] timeout、max tokens、streaming、fallback 行为有测试。
- [ ] 环境契约如有变化，三处同步并通过 `test_settings.py`。
- [ ] README 与 `docs/progress.md` 同步。

## 进度更新

`docs/progress.md` **46** → 实现完成后改为 `✅`。
