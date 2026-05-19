# 02 - 配置层 settings + .env 契约

## 依赖

01

## 目标

`agent/src/settings/config.py`从环境变量加载配置；`.env.example` 与代码字段一一对应。

## 范围

- Pydantic Settings（或 dataclass + os.getenv）
- 字段与 [01-project-init.md](./01-project-init.md) **环境变量清单**一一对应，至少包括：
  - LangSmith：`LANGSMITH_API_KEY`、`LANGCHAIN_TRACING_V2`、`LANGCHAIN_PROJECT`、`LANGCHAIN_ENDPOINT`
  - LLM（SiliconFlow）：`OPENAI_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_MODEL_NAME`
  - Embedding / Rerank：`EMBEDDING_MODEL`、`EMBEDDING_MODEL_DIMS`、`RERANK_MODEL`、`RERANK_TOP_K`
  - Qdrant：`QDRANT_HOST`、`QDRANT_PORT`、`QDRANT_COLLECTION_KB`（可提供 `qdrant_url` 属性拼接 `http://{host}:{port}`）
  - Postgres：`DATABASE_URL`
  - Gateway：`AGENT_HOST`、`AGENT_PORT`
- 若库要求 `LANGCHAIN_API_KEY` 而 env 仅有 `LANGSMITH_API_KEY`，在 Settings 内做 fallback，不新增重复 .env key
- 单例 `get_settings()` 便于测试 override

## 非范围

- 连接池、迁移

## 实现要点

- 修改 `.env` 时 **必须** 同步 `.env.example`，示例值用 `***` 掩码
- 提供 `agent/tests/test_settings.py`

## 测试方案

```bash
cd agent
uv run pytest tests/test_settings.py -v
uv run python -c "from settings.config import get_settings; s=get_settings(); assert s.AGENT_PORT"
```

**通过标准**：pytest 全绿；缺必填 env 时有明确错误（可用 monkeypatch 测）。

## 完成标准

- 所有 PRD 相关配置项有类型与默认值（仅非敏感项）
- 文档注释说明每项用途

## 进度更新

`docs/progress.md` **02** → `✅`
