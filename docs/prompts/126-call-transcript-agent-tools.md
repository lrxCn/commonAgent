# 126 - 通话转写：Back internal 查询与 Agent 只读 tool

## 建议执行模型

- 模型：GPT-5 或同档强编码模型
- Reasoning：high
- 原因：跨 Back internal 鉴权、Agent 环境契约、DeepAgents tool 挂载与 `user_id` 隔离，易踩边界。

## 新窗口执行规则

1. 先读 `AGENTS.md`、`README.md`、`docs/progress.md` 与本任务卡。
2. 阅读 PRD：[call-transcript-persistence.md](../prd/call-transcript-persistence.md)（internal API、tool 表、开放问题 #2/#3 默认决议）。
3. 核对 **124** 已完成；阅读 `agent/src/graph/supervisor.py`、`agent/src/graph/executors.py`、`back/src/services/forward.py`（`X-Internal-Key` 模式）。
4. 实现 Back **`/internal/calls/transcripts`** + Agent **`list_call_transcripts` / `get_call_transcript`**；tool **仅挂 DEEPAGENTS** 路径（默认决议）。
5. 测试通过后更新 progress **126** → `✅`。
6. 自动 git commit；不 push。

## 依赖

124

## 背景

Agent 通过 HTTP 调 Back 读 Postgres 原文（**不向量化**）。`user_id` 必须来自 `GraphContextSchema`，禁止信任模型在 tool 参数里传的 user_id。Back internal 路由校验 `X-Internal-Key`（与现有 `INTERNAL_API_KEY` 对齐）。

## 目标

### Back

- `GET /internal/calls/transcripts`：query `user_id`（必填，由 Agent 从 context 注入）、可选 `peer_user_id`、`since`、`until`、`limit`（默认 5，上限 20）；返回元数据列表（含 `call_id`、`peer_display_name`、`ended_at`、`duration_ms`、`line_count`）。
- `GET /internal/calls/transcripts/{call_id}`：query `user_id`；返回完整 `lines`；超长时 `truncated: true` + `total_lines`（PRD 默认）。
- 复用 **124** service；internal 路由单独模块 + `Depends(require_internal_key)`。

### Agent

- Settings：`BACK_URL`（默认 `http://127.0.0.1:8080`）、`INTERNAL_API_KEY`（与 Back 一致）；同步 `agent/.env.example` 与 `agent/.env` 注释（不提交真实密钥）。
- `agent/src/tools/call_transcripts.py`（名可调整）：两个 LangChain tool，内部 httpx 调 Back。
- 将 tools 注册到 **DeepAgents / Supervisor** 执行路径（`build_supervisor_agent` 或 deepagents 节点）；**不**挂 `SMALL_CHAT` / `memory_query` / `RAG_ANSWER`。
- 单测：mock Back HTTP；`user_id` 来自 context；错误 404/502 可读 message。

## 范围

| 模块 | 变更 |
|------|------|
| `back/src/api/internal_routes.py`（或等价） | internal GET + key 校验 |
| `back/src/api/deps.py` | `require_internal_key`（若无则新增） |
| `back/src/api/app.py` | include internal router |
| `back/tests/test_call_transcripts_internal.py` | internal 鉴权与隔离 |
| `agent/src/settings/config.py` | `BACK_URL` |
| `agent/.env.example` | `BACK_URL`、`INTERNAL_API_KEY` |
| `agent/src/tools/call_transcripts.py` | tool 实现 |
| `agent/src/graph/supervisor.py` 或 executor 挂载点 | `tools=[...]` 仅 deepagents 路径 |
| `agent/tests/test_call_transcript_tools.py` | mock Back |

## 实施步骤

1. Back internal deps：校验 header `X-Internal-Key`。
2. 实现 list/get handlers，强制 `user_id` query 与 DB 过滤一致。
3. Agent HTTP client：与 Back forward 对称的 key header。
4. 定义 tool schema 与 docstring（指导模型先 list 再 get）。
5. 在 `choose_executor` / supervisor  wiring 处仅 DEEPAGENTS 传入 tools。
6. `cd back && uv run pytest tests/test_call_transcripts_internal.py tests/test_call_transcripts.py -v`
7. `cd agent && uv run pytest tests/test_call_transcript_tools.py -v`

## 验证方案

```bash
cd back && uv run pytest tests/test_call_transcripts_internal.py tests/test_call_transcripts.py -v
cd agent && uv run pytest tests/test_call_transcript_tools.py -v
```

## 非范围

- Front 上报（**125**）
- 每轮 chat 自动注入 transcript
- langmem 写入通话全文
- README / demo B7（**127**）
- 向量检索

## 完成标准

- [ ] Agent 仅能查 context 对应 `user_id` 的记录。
- [ ] internal 无 key 拒绝；browser 无法访问 internal。
- [ ] tool 仅在 DEEPAGENTS（或文档约定的 supervisor）路径可用。
- [ ] 上述 pytest 绿。
- [ ] progress **126** → `✅`。
- [ ] git commit。

## 进度更新

`docs/progress.md` **126** → `✅`；建议下一步 **127**（依赖 125+126）。
