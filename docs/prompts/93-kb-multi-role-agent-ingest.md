# 93 - KB 多角色：Agent ingest 与 documents API `role_ids[]`

## 建议执行模型

- 模型：GPT-5 或同档强编码模型
- Reasoning：high
- 原因：触及 ingest schema、Qdrant payload 与 KB list/get/delete 契约变更；需与现有 `test_kb_ingest.py` 对齐。

## 新窗口执行规则

1. 先读根目录 `AGENTS.md`、`README.md`、`docs/progress.md` 与本任务卡。
2. 阅读 PRD：[kb-multi-role-rag.md](../prd/kb-multi-role-rag.md) §D1、§Agent Internal API。
3. 核对 **87**（对话侧 `role_ids[]` OR 检索）已完成；本任务补齐 **文档侧** ingest payload。
4. 只实现本任务范围；README 大改留 **98**。
5. 测试通过后更新 `docs/progress.md` 并 git commit。

## 依赖

87

## 背景

对话 RAG 已支持用户 `context.role_ids[]` OR 检索（任务 87），但 KB ingest 与 Qdrant payload 仍为单值 `role_id`。本任务将 Agent 内网 KB 契约统一为 `role_ids: string[]`（minItems=1），并按 `doc_id` 唯一标识文档，移除 list/get/delete 上的 `role_id` query。

## 目标

- `KbIngestRequest` / gateway schemas：`role_id` → **`role_ids: list[str]`**（非空、去重、trim）；**不再接受**单值 `role_id` 业务入参。
- `rag/ingest.py`：每个 chunk point payload 写入 **`role_ids[]`**（完整数组）；迁移期可双写 `role_id` 供 **94** fallback，或本任务仅写 `role_ids`（与 PRD M1 一致）。
- `rag/kb_documents.py` + gateway routes：
  - `GET /internal/kb/documents`：支持 query `role_id` 重复或多值 → 返回 payload **`role_ids` 与查询集合有交集** 的文档摘要（按 `doc_id` 去重）。
  - `GET /internal/kb/documents/{doc_id}`：**移除** query `role_id`。
  - `DELETE /internal/kb/documents/{doc_id}`：**移除** query `role_id`；删除该 `doc_id` 全部 points。
- 更新/新增 pytest：`test_kb_ingest.py`、`test_kb_admin_api.py` 覆盖单角色与多角色 ingest。

## 范围

| 模块 | 变更 |
|------|------|
| `agent/src/gateway/schemas_ingest.py` | `role_ids[]` |
| `agent/src/rag/ingest.py` | payload `role_ids[]` |
| `agent/src/rag/kb_documents.py` | list/get/delete 按 `doc_id` |
| `agent/src/gateway/ingest.py` 等 | 路由参数 |
| `agent/tests/test_kb_ingest.py` | 多角色 ingest |
| `agent/tests/test_kb_admin_api.py` | list/get/delete 契约 |

## 实施步骤

1. 将 ingest request schema 改为 `role_ids: list[str]`，校验非空与各 id 格式。
2. ingest 路径向 Qdrant upsert 时 payload 携带相同 `role_ids[]`。
3. kb documents list：scroll/filter 按 query role 集合与 payload `role_ids` 交集；get/delete 仅 `doc_id`。
4. 更新现有测试与 mock fixture；补多角色单 doc 只 ingest 一次用例。

## 验证方案

```bash
cd agent && uv run pytest tests/test_kb_ingest.py tests/test_kb_admin_api.py -v
cd agent && uv run ruff check src tests
```

## 非范围

- RAG 对话检索 filter 对 payload `role_ids[]` 的读取（**94**）
- Back meta / junction 表（**95**）
- Front UI（**96**）
- 数据迁移（**97**）
- README / demo-walkthrough（**98**）

## 完成标准

- [ ] ingest 一次写入多 `role_ids`，每个 point payload 含相同数组。
- [ ] list/get/delete 不再要求 query `role_id`（list 筛选仍可用 role query）。
- [ ] 相关 pytest 通过。
- [ ] progress **93** → `✅`。
- [ ] git commit（仅本任务相关文件）。

## 进度更新

`docs/progress.md` **93** → `✅`；建议下一步 **94**。
