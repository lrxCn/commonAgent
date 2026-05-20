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

3. 启动内网 Gateway（HTTP，任务 05+）：

```bash
uv run uvicorn main:app --host 127.0.0.1 --port 18080
# 或使用 .env 中的 AGENT_HOST / AGENT_PORT：
uv run python -m main
```

默认 `AGENT_HOST=0.0.0.0` 便于容器内监听；**生产环境应仅在内网/VPC 暴露该端口**（防火墙、Service Mesh 或反向代理限制），勿对公网开放。

## 环境变量说明

完整 key 列表见 [.env.example](./.env.example)，与项目统一契约一致：

| 分组 | 说明 |
|------|------|
| LangSmith | `LANGSMITH_API_KEY`、`LANGCHAIN_*`；不需要追踪时可设 `LANGCHAIN_TRACING_V2=false` |
| LLM | `OPENAI_API_KEY` + `OPENAI_BASE_URL` 对接 SiliconFlow，模型见 `OPENAI_MODEL_NAME` |
| Embedding / Rerank | `EMBEDDING_MODEL`、`EMBEDDING_MODEL_DIMS`（须与 Qdrant 向量维度一致，默认 1024）、`RERANK_*` |
| Qdrant | `QDRANT_HOST`、`QDRANT_PORT`、`QDRANT_COLLECTION_KB`、`QDRANT_COLLECTION_MEM0` |
| mem0 | `MEM0_MOCK`、`MEM0_READ_LIMIT`；写入走 `Memory.add(..., infer=True)` + `custom_instructions` |
| Postgres | `DATABASE_URL`（LangGraph Checkpointer，见下文） |
| Gateway | `AGENT_HOST`、`AGENT_PORT`（任务 05 起用） |

**切勿将真实 `.env` 提交到 git**；仅维护掩码后的 `.env.example`。

## Postgres Checkpointer（对话持久化）

LangGraph 通过 `thread_id` 将会话状态写入 Postgres。连接串格式：

```text
postgresql://<用户>:<密码>@<主机>:<端口>/<数据库名>
```

路径最后一段是**数据库名**（项目约定为 `common_agent`），与 Docker/OrbStack **容器名**无关。

### 本地 Postgres

使用你本机已有的实例（如 OrbStack 里的 `my-postgres`）：

1. 确认容器将 `5432` 映射到本机。
2. 若尚无 `common_agent` 库，在容器内创建：

```bash
docker exec -it my-postgres psql -U postgres -c "CREATE DATABASE common_agent;"
```

3. 在 `agent/.env` 中配置 `DATABASE_URL`，用户名、密码、库名与实例一致，例如：

```env
DATABASE_URL=postgresql://postgres:<你的密码>@localhost:5432/common_agent
```

### 代码中使用

```python
from memory.checkpointer import get_checkpointer, get_pooled_checkpointer

# 测试或短生命周期
with get_checkpointer() as checkpointer:
    graph = builder.compile(checkpointer=checkpointer)

# 长期运行的服务（连接池）
checkpointer = get_pooled_checkpointer()
graph = builder.compile(checkpointer=checkpointer)
```

首次连接会自动执行 `checkpointer.setup()` 建表。

## mem0 用户偏好（本地 OSS + Qdrant）

- 读取/写入均使用 `mem0ai` 包的自托管 **`Memory`**，向量落在 `QDRANT_COLLECTION_MEM0`（与 KB collection 分离）。
- **禁止** mem0 托管云、`MemoryClient`、`MEM0_API_KEY`。
- post_turn 将本轮 `user` / `assistant` 原文交给 `Memory.add(..., infer=True)`；抽取与 hash 去重由 mem0 负责，规则见 `src/memory/prompts/mem0_custom_instructions.txt`。
- mem0 会在 `~/.mem0/history.db`（或环境变量 `MEM0_DIR`）维护辅助 SQLite；向量仍在 Qdrant。多实例部署时请统一 `MEM0_DIR` 或接受每实例独立 history 文件。

### 从任务 17（`infer=False`）迁移

旧写入格式为 `User preference facts:\n- ...` 包装文本，与新管线生成的短句事实 **hash 不同**，短期可能并存。上线前建议在开发/测试环境对 `QDRANT_COLLECTION_MEM0` 执行其一：

1. **推荐**：按 `user_id` 清空或重建 collection（Qdrant UI / API `delete_collection` 后重启 Agent 让 mem0 重建）。
2. **或**：删除 `payload.data` 以 `User preference facts:` 开头的 point。

生产 rollout 时在变更单中记录上述步骤。

## LangSmith 追踪

在 `agent/.env` 中配置（见 [.env.example](./.env.example)）：

```env
LANGSMITH_API_KEY=lsv2_***
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=common-agent
```

关闭追踪时设 `LANGCHAIN_TRACING_V2=false`（无需删除 API Key）。Gateway 与图编译时会调用 `configure_tracing_from_settings()`，将 Settings 同步到进程环境变量。

### 在 UI 查看一轮对话

1. 打开 [LangSmith](https://smith.langchain.com/) → 选择项目名（与 `LANGCHAIN_PROJECT` 一致，默认 `common-agent`）。
2. 本地发起一轮对话，例如 Gateway：

   ```bash
   curl -s -X POST http://127.0.0.1:18080/internal/chat \
     -H "Content-Type: application/json" \
     -d '{"thread_id":"demo-1","message":"你好","context":{"user_id":"u1","role_id":"default"}}'
   ```

3. 在 LangSmith **Traces** 列表按时间找到该次 `invoke`；展开可看到 LangGraph 节点链，以及带标签的子 span：
   - `rewrite`、`rag_router`、`retrieve`、`rerank`（metadata 含 `rerank=true`）、`supervisor`、`guardrails_inbound` / `guardrails_outbound`
4. 点击 run 的 **Metadata** 查看 RAG 命中数、护栏拦截原因等；**不会**记录完整 API Key。长文本可通过环境变量 `LANGCHAIN_TRACE_MESSAGE_MAX_CHARS`（默认 500）截断。
5. **Rewrite 条件跳过**（任务 26，目标态）：寒暄等轮次 `rewrite` span 的 metadata 含 `rewrite_skipped=true`、`rewrite_skip_reason`（如 `chitchat`），且无子 LLM 调用；可通过 `REWRITE_SKIP_ENABLED=false` 恢复每轮 LLM 改写。见 [26-rewrite-conditional-skip](../docs/prompts/26-rewrite-conditional-skip.md)。

可选：使用独立 test project key 跑一条真实 invoke 后在 UI 人工核对（CI 不依赖外网）。

### 导出 trace（CLI）

在 `agent/` 目录执行（自动加载 `.env`，拉取当前项目最新一条 root trace）：

```bash
./scripts/fetch_trace.sh --latest
```

- 输出目录：`logs/`
- 文件名：`{UTC开始时间}_{run名}_{id前8位}.json`，例如 `20260519_232654_agent_019e4290.json`
- 默认内容为摘要 JSON（各 span 状态、耗时、metadata 等）

可选：

```bash
./scripts/fetch_trace.sh --latest --full           # 完整 inputs/outputs
./scripts/fetch_trace.sh --latest --last-minutes 30  # 仅在最近 30 分钟内取最新
```

`logs/*.json` 已加入 `.gitignore`，勿将导出文件提交到 git。

## 测试与 lint

```bash
make test
make integration-tests   # 需配置模型 API Key
make lint
make format

# Checkpointer（任务 03）
uv run pytest tests/test_checkpointer.py -v -m "not integration"
uv run pytest tests/test_checkpointer.py -v -m integration   # 需 DATABASE_URL 可连

# Gateway（任务 05）
uv run pytest tests/test_gateway_health.py -v

# LangSmith tracing（任务 21）
uv run pytest tests/test_tracing.py -v
```

## 参考

- [docs/architecture.md](../docs/architecture.md)
- [docs/prompts/](../docs/prompts/) 任务卡
- Deep Agents 文档：https://docs.langchain.com/oss/python/deepagents/overview
