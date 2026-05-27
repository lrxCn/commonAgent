# 124 - 通话转写：Back 表结构与 POST 持久化

## 建议执行模型

- 模型：GPT-5 或同档强编码模型
- Reasoning：medium
- 原因：Alembic 迁移、ORM、鉴权与 upsert 契约需与 PRD 一致；范围集中在 Back。

## 新窗口执行规则

1. 先读 `AGENTS.md`、`README.md`、`docs/progress.md` 与本任务卡。
2. 阅读 PRD：[call-transcript-persistence.md](../prd/call-transcript-persistence.md)（数据模型、POST API、开放问题默认决议）。
3. 核对 **117**（Front `finalLines` / console dump）与 **111**（`call_id`）已落地；阅读 `back/src/api/call_routes.py`、`back/src/db/models.py`、现有 Alembic 修订风格。
4. 只实现 Back **存储 + `POST /api/calls/{call_id}/transcript`**；不做 Front、不做 Agent tool、不做 internal GET（**126**）。
5. 测试通过后更新 `docs/progress.md` **124** → `✅`；本任务 **不** 改 README 全文（**127** 收口），可在 progress 备注 API 已就绪。
6. 自动 git commit；不 push。

## 依赖

117（ASR 双轨 transcript 聚合已存在）

## 背景

挂断时 Front 将上报分角色 ASR 原文；Back 在 Postgres `common_agent_back` 以 **JSONB 结构化存储**（不向量化）。一期 `(user_id, call_id)` **upsert**，信令 hub 销毁后仍接受 POST（Session + `peer_user_id` 校验为主）。

## 目标

- Alembic 迁移：`call_transcripts` 表（字段见 PRD）。
- ORM `CallTranscript` + repository/service：`upsert_transcript(...)`。
- **`POST /api/calls/{call_id}/transcript`**：Cookie Session；`user_id` 来自 Session；body 含 `peer_user_id`、`peer_display_name`、`started_at`、`ended_at`、`duration_ms`、`lines[]`。
- 校验：`lines` 非空；`peer_user_id` 非空且 ≠ 当前用户；`call_id` 路径与 body 一致（若 body 也带 call_id）。
- 响应：`201` 新建 / `200` upsert；`{ "id", "call_id" }`。
- 单测：未登录 401；upsert 幂等；用户隔离（用户 A 不能写 B 的 user_id）。

## 范围

| 模块 | 变更 |
|------|------|
| `back/alembic/versions/` | 新 revision `call_transcripts` |
| `back/src/db/models.py` | `CallTranscript` |
| `back/src/services/call_transcripts.py`（名可调整） | upsert / 查询（查询供 126 复用可先写 service 方法） |
| `back/src/api/call_routes.py` 或 `call_transcript_routes.py` | POST 路由 |
| `back/tests/test_call_transcripts.py` | 新测试文件 |

## 实施步骤

1. 按 PRD 建表：`id` UUID PK、`call_id`、`user_id`、`peer_user_id`、`peer_display_name`、`started_at`、`ended_at`、`duration_ms`、`lines` JSONB、`created_at`；唯一 `(user_id, call_id)`。
2. Pydantic schema：`TranscriptLine`（`track`、`role_label`、`text`、`start_time?`、`end_time?`、`seq`）、`CallTranscriptUpsertBody`。
3. POST handler：Session 用户写入 `user_id`；调用 upsert。
4. 日志：仅 `call_id` + `line_count`，不打印全文。
5. `cd back && uv run pytest tests/test_call_transcripts.py -v`（及必要时 `tests/test_demo_database.py` 确保迁移链）。

## 验证方案

```bash
cd back && uv run pytest tests/test_call_transcripts.py -v
```

## 非范围

- Front POST 上报（**125**）
- `GET /api/calls/transcripts` 对外列表（**127** 或三期 UI）
- Back `/internal/calls/transcripts`（**126**）
- Agent tool、README/demo 收口（**127**）
- 向量 / langmem / 信令 hub 元数据表加固

## 完成标准

- [ ] Alembic head 含 `call_transcripts` 表。
- [ ] `POST /api/calls/{call_id}/transcript` 鉴权与 upsert 行为符合 PRD。
- [ ] `test_call_transcripts.py` 绿。
- [ ] progress **124** → `✅`。
- [ ] git commit。

## 进度更新

`docs/progress.md` **124** → `✅`；建议下一步 **125**（可与 **126** 并行，均依赖 124）。
