# 01 - 项目骨架与 uv/deepagents 初始化

## 依赖

无（首任务）

## 目标

创建 `front/`、`back/`、`agent/` 三目录；在 `agent/` 用 **uv** 初始化 Python 项目，用 **langgraph-cli** 初始化 deepagents 骨架；配置 `.gitignore` 忽略 `.env`；落地 **项目统一的 `.env.example` 契约**（与本地 `.env` 同 key，示例值全部掩码）。

## 范围

- 根目录 `.gitignore`：`.env`、`**/.env`、`__pycache__`、`.venv` 等
- `agent/pyproject.toml` + `uv.lock`（若 lock 生成失败可后续补）
- `agent/.env.example`：**必须**与下方「环境变量清单」一致（值用 `***` / 占位，禁止真实密钥入库）
- `agent/README.md`：本地启动说明（`cp .env.example .env` 后填入 SiliconFlow / LangSmith 等）
- `front/README.md`、`back/README.md`：占位说明

## 非范围

- 业务逻辑、Gateway、图节点
- `settings/config.py` 映射（任务 **02**）
- 本地真实 `.env` 内容提交到 git

## 环境变量清单（`.env.example` 权威模板）

实现时在 `agent/.env.example` 中按此结构创建；**分组与 key 名不可擅自改名**（任务 02 的 Settings 将逐字段映射）。

```bash
# --- LangSmith ---
LANGSMITH_API_KEY=lsv2_***
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=common-agent
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com

# --- LLM：SiliconFlow（OpenAI 兼容）---
OPENAI_API_KEY=sk-***
OPENAI_BASE_URL=https://api.siliconflow.cn/v1
OPENAI_MODEL_NAME=Pro/deepseek-ai/DeepSeek-V3.2

# --- Embedding（SiliconFlow 同平台或 OpenAI 兼容 embedding 接口）---
EMBEDDING_MODEL=BAAI/bge-large-zh-v1.5
EMBEDDING_MODEL_DIMS=1024

# --- Rerank ---
RERANK_MODEL=BAAI/bge-reranker-v2-m3
RERANK_TOP_K=10

# --- Qdrant ---
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION_KB=common_agent_kb

# --- Postgres Checkpointer（任务 03 起用；第一期 init 先占位）---
DATABASE_URL=postgresql://postgres:***@localhost:5432/common_agent

# --- Gateway（任务 05 起用；可先保留默认）---
AGENT_HOST=0.0.0.0
AGENT_PORT=18080
```

### 约定说明

| 项 | 说明 |
|----|------|
| **LLM** | 统一走 `OPENAI_*` + `OPENAI_BASE_URL`，对接 SiliconFlow，不单独引入多家 SDK |
| **Embedding / Rerank** | 模型名用 SiliconFlow 支持的 ID；`EMBEDDING_MODEL_DIMS` 须与 Qdrant collection 向量维度一致（1024） |
| **RERANK_TOP_K** | 送入 rerank 的候选上限（整数），非「启用开关」 |
| **Qdrant** | 用 `HOST`+`PORT`；代码层可拼 `http://{host}:{port}`（任务 02） |
| **LangSmith** | `LANGSMITH_API_KEY` 为 Smith 控制台 key；若某库只认 `LANGCHAIN_API_KEY`，在 Settings 中做别名读取，**.env.example 仍以本清单为准** |
| **本地 `.env`** | 开发者自建，**绝不提交**；与 `.env.example` key 对齐即可 |

## 实现要点

1. `mkdir -p front back agent`
2. `cd agent && uv init`（或等价）
3. 安装：`deepagents`、`langgraph`、`langgraph-cli`（版本以 deepagents 文档为准）
4. `langgraph new` 或项目模板初始化 graph 目录（保留可扩展结构）
5. 从本任务卡复制上述块生成 `agent/.env.example`（掩码化所有 secret）
6. README 写明：LLM/Embedding/Rerank 依赖 SiliconFlow；LangSmith 可选关闭 `LANGCHAIN_TRACING_V2=false`
7. **不要**把用户提供的真实 `.env` 写入仓库

## 产出文件（检查清单）

- [ ] `front/README.md`
- [ ] `back/README.md`
- [ ] `agent/pyproject.toml`
- [ ] `agent/.env.example`（key 与上文清单一致）
- [ ] `.gitignore`

## 测试方案

```bash
cd agent
uv sync
uv run python -c "import langgraph; print('ok')"
test -f .env.example
# 校验必备 key 存在（不要求本地有 .env）
for key in LANGSMITH_API_KEY OPENAI_API_KEY OPENAI_BASE_URL EMBEDDING_MODEL QDRANT_HOST DATABASE_URL; do
  grep -q "^${key}=" .env.example || { echo "missing $key"; exit 1; }
done
grep -q 'sk-\*\*\*' .env.example && grep -q 'lsv2_\*\*\*' .env.example && echo "masked ok"
test -d ../front && test -d ../back && echo "dirs ok"
```

**通过标准**：`uv sync` 成功；`import langgraph` 无报错；三目录存在；`.env.example` 含清单内全部 key 且无明文密钥。

## 完成标准

- 三目录存在，agent 可 `uv run`
- `.env` 在 gitignore 中
- `.env.example` 与本文「环境变量清单」一致（含 SiliconFlow + LangSmith + Qdrant + Postgres 占位）

## 进度更新

在 `docs/progress.md` 将 **01** 标为 `✅`，填写完成日；总览「已完成」+1。
