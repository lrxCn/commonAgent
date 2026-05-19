# commonAgent — Agent 服务

基于 [deepagents](https://docs.langchain.com/oss/python/deepagents/overview) 与 LangGraph 的智能体主服务（`langgraph new` deepagents-python 模板）。

## 环境要求

- Python ≥ 3.11
- [uv](https://docs.astral.sh/uv/)
- LLM / Embedding / Rerank： [SiliconFlow](https://siliconflow.cn/)（OpenAI 兼容 API）
- 可选：[LangSmith](https://smith.langchain.com/) 追踪（关闭时设 `LANGCHAIN_TRACING_V2=false`）

## 本地启动

1. 安装依赖并配置环境变量：

```bash
cd agent
uv sync
cp .env.example .env
# 编辑 .env：填入 SiliconFlow 的 OPENAI_API_KEY 等；LangSmith 可选
```

2. 启动 LangGraph 开发服务：

```bash
uv run langgraph dev
```

## 环境变量说明

完整 key 列表见 [.env.example](./.env.example)，与项目统一契约一致：

| 分组 | 说明 |
|------|------|
| LangSmith | `LANGSMITH_API_KEY`、`LANGCHAIN_*`；不需要追踪时可设 `LANGCHAIN_TRACING_V2=false` |
| LLM | `OPENAI_API_KEY` + `OPENAI_BASE_URL` 对接 SiliconFlow，模型见 `OPENAI_MODEL_NAME` |
| Embedding / Rerank | `EMBEDDING_MODEL`、`EMBEDDING_MODEL_DIMS`（须与 Qdrant 向量维度一致，默认 1024）、`RERANK_*` |
| Qdrant | `QDRANT_HOST`、`QDRANT_PORT`、`QDRANT_COLLECTION_KB` |
| Postgres | `DATABASE_URL`（Checkpointer，任务 03 起用） |
| Gateway | `AGENT_HOST`、`AGENT_PORT`（任务 05 起用） |

**切勿将真实 `.env` 提交到 git**；仅维护掩码后的 `.env.example`。

## 测试与 lint

```bash
make test
make integration-tests   # 需配置模型 API Key
make lint
make format
```

## 参考

- [docs/architecture.md](../docs/architecture.md)
- [docs/prompts/](../docs/prompts/) 任务卡
- Deep Agents 文档：https://docs.langchain.com/oss/python/deepagents/overview
