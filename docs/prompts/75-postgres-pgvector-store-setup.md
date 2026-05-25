# 75 - LangMem Store 前置：Postgres + pgvector 运维配置

## 建议执行模型

- 模型：GPT-5.4 或同等级
- Reasoning：medium
- 原因：以文档与验证命令为主，需核对 Docker/SQL 与 Agent 现有 `DATABASE_URL`、`EMBEDDING_MODEL_DIMS` 契约。

## 新窗口执行规则

1. 先读根目录 `AGENTS.md`、`README.md`、`docs/progress.md` 和本任务卡。
2. 阅读 PRD：[agent-langmem-migration.md](../prd/agent-langmem-migration.md)。
3. 只实现本任务范围（Postgres pgvector 运维说明 + README 章节 + 验证步骤）。
4. 按本任务测试计划验证（至少本地 SQL 检查通过）。
5. 测试通过后更新 `docs/progress.md`。
6. 自动创建 git commit；不要自动 push，除非用户明确要求。

## 依赖

无（可与 LangMem 迁移任务 69 并行；**任务 70 开始前须完成本任务或确认 pgvector 已就绪**）。

## 背景

LangMem 迁移后，用户长期记忆落在 **LangGraph Postgres Store**（与 checkpoint **同一 `DATABASE_URL` 库**）。存储分两层：

| 层 | 内容 | 怎么读 | 要不要 pgvector |
|----|------|--------|-----------------|
| **Profile** | 姓名、城市、公司等结构化字段 | 按 `user_id + attribute` 直接 `get` | **不要** |
| **Collection** | 闲聊 inferred 的自由文本事实 | 按当前问题做 **语义相似度 search** | **要** |

两层 **共存**：同一用户可以同时有 profile 字段和 collection 条目。Collection 的语义检索依赖 Postgres **`pgvector` 扩展**。

**已确认**：不做 Qdrant mem0 数据迁移；Qdrant 里旧用户记忆可丢。

## 目标

- 在 README 增加「Postgres + pgvector（LangGraph Store）」运维章节，可复制执行。
- 说明与现有 checkpoint 共用库时的注意事项（同库、不同表；Store 首次 `setup()` 建表）。
- 提供验证清单：extension 已装、维度与 `EMBEDDING_MODEL_DIMS` 一致、Store 可 `setup()`。

## 范围

| 模块 | 变更 |
|------|------|
| `README.md` | 新增 Postgres pgvector + Store 小节（本地 Docker / 已有实例两种路径） |
| `docs/prd/agent-langmem-migration.md` | 如需，补充指向本任务卡的链接（若尚未链接） |
| `docs/progress.md` | 任务 75 状态 |

## 非范围

- 不实现 `memory/store.py`（任务 70）。
- 不安装或修改 Agent 业务代码、不删 mem0（任务 73）。
- 不要求改 RAG 用的 Qdrant。

---

## 一、推荐：Docker 使用带 pgvector 的 Postgres 镜像

若本地仍用普通 `postgres` 镜像，需换镜像或自行编译 extension。推荐：

```bash
# 拉取带 pgvector 的官方衍生镜像（版本按团队习惯 pin）
docker pull pgvector/pgvector:pg16

# 若已有容器 my-postgres，可新建独立容器或重建；示例新建：
docker run -d \
  --name common-agent-pg \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=common_agent \
  -p 5432:5432 \
  pgvector/pgvector:pg16
```

`agent/.env` 中 `DATABASE_URL` 示例（与 checkpoint 相同）：

```text
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/common_agent
```

## 二、在目标库启用 pgvector

进入容器或任意 `psql` 客户端，对 **`DATABASE_URL` 指向的库** 执行：

```sql
-- 1. 安装扩展（每个 database 一次）
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. 确认
SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';
```

期望：`extname = vector`，有版本号。

**已有普通 Postgres、不能换镜像时**：需在服务器安装 pgvector 包后再 `CREATE EXTENSION vector`；具体命令因 OS 而异，README 中注明「需 DBA 安装 pgvector」并链到 https://github.com/pgvector/pgvector 。

## 三、与 LangGraph Checkpointer 的关系

| 组件 | 用途 | 表 |
|------|------|-----|
| `PostgresSaver`（已有） | thread 对话 checkpoint | LangGraph checkpoint 表（已存在） |
| `PostgresStore`（迁移后） | 用户长期记忆 namespace/key | Store 迁移 `setup()` **新建** 的表 |

**同一 `DATABASE_URL`、同一 database** 即可；无需第二个库。  
首次启动 Store 客户端时调用 `store.setup()`（任务 70 实现；运维文档说明「部署前或首次启动会自动 migrate」）。

## 四、向量维度必须与 Embedding 一致

Agent 已配置（见 `agent/.env.example`）：

- `EMBEDDING_MODEL` — 生成向量用的模型
- `EMBEDDING_MODEL_DIMS` — 向量维度（如 `1024`、`1536`）

LangGraph Store 的 pgvector index **必须**使用相同 `dims`。任务 70 会从 settings 读取；运维文档须写清：

> 若更换 embedding 模型导致维度变化，需按 LangGraph Store 文档 **重建 index** 或清空 Store 记忆表后重新 `setup()`（与 Qdrant KB 重建类似，用户记忆可丢时可直接清空 Store 表）。

## 五、验证清单（本任务完成标准）

在 README 中给出以下命令，执行者勾选：

```bash
# 1. 连接库
psql "$DATABASE_URL" -c "SELECT 1"

# 2. pgvector
psql "$DATABASE_URL" -c "SELECT extname FROM pg_extension WHERE extname = 'vector';"

# 3. checkpoint 仍可用（已有测试）
cd agent && uv run pytest tests/test_checkpointer*.py -v -k "not integration" 2>/dev/null || true
# 有 integration Postgres 时跑完整 checkpointer 测试
```

可选（任务 70 完成后补测）：

```bash
# Store setup smoke（70 实现后）
cd agent && uv run python -c "
from memory.store import get_pooled_store
store = get_pooled_store()
store.setup()
print('store setup ok')
"
```

## 六、生产注意（文档简述）

- 备份：Store 表与 checkpoint 表同在 Postgres，按现有 DB 备份策略即可。
- 连接池：Store 与 Checkpointer 各用独立 pool（任务 70）；注意 `max_connections`。
- pgvector 索引：数据量大后再调 `lists` 等 HNSW 参数；第一期默认值即可。

## 验证方案

```bash
# 文档任务：人工按 README 新章节执行 SQL 验证
psql "$DATABASE_URL" -c "CREATE EXTENSION IF NOT EXISTS vector;"
psql "$DATABASE_URL" -c "SELECT extname FROM pg_extension WHERE extname = 'vector';"
```

## 完成标准

- [ ] README 含 pgvector 安装/启用步骤（Docker + 已有实例说明）。
- [ ] 说明 Store 与 checkpoint 同库、embedding 维度约束。
- [ ] `docs/progress.md` 任务 75 标记完成。

## 进度更新

`docs/progress.md` **75** → 实现完成后改为 `✅`。
