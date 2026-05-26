# 89 - 演示平台 Phase 3a：Agent KB list/get/delete + Back kb_document_meta 双写

## 建议执行模型

- 模型：GPT-5 或同档强编码模型
- Reasoning：high
- 原因：跨 Agent 内网 API 与 Back 元数据一致性；ingest 成功后才 upsert meta。

## 新窗口执行规则

1. 先读 PRD 模块三（RAG 管理）、Agent 内网 API 表。
2. 核对 **81**、**86**、**87** 已完成。
3. **禁止**仅靠 Qdrant scroll 拼原文；正文以 `kb_document_meta.raw_content` 为准。

## 依赖

81, 86, 87

## 背景

向量在 Qdrant（Agent）；列表/编辑原文在 Back `kb_document_meta`。新建/编辑 = Agent ingest + Back upsert meta。

## 目标

- Agent 新增：
  - `GET /internal/kb/documents`（按 `role_id`；或支持 query 多 role）
  - `GET /internal/kb/documents/{doc_id}?role_id=`
  - `DELETE /internal/kb/documents/{doc_id}?role_id=`
- Back `POST /api/admin/kb/documents`：admin 校验 → 转发 ingest → 成功 upsert meta（含 `raw_content`、`chunks_written`、`tokens_estimated` 等）。
- Back `GET/PATCH/DELETE` admin KB 路由代理 Agent + 读/写 meta。
- 上传限制：≤2MB；`.txt`/`.md`；UTF-8。

## 范围

| 模块 | 变更 |
|------|------|
| `agent/src/gateway/` | kb list/get/delete |
| `agent/tests/test_kb_*.py` | 新端点 |
| `back/src/admin/kb.py` | 双写与代理 |
| `back/tests/test_demo_kb.py` | meta 与 mock Agent |

## 验证方案

```bash
cd agent && uv run pytest tests/test_kb_admin_api.py -v
cd back && uv run pytest tests/test_demo_kb.py -v
```

## 非范围

- Front RAG 管理 UI（**90**）
- 演示 walkthrough 文档（**92**）

## 完成标准

- [ ] ingest 成功后 meta 可查 `raw_content`。
- [ ] delete 后 Agent 列表与 meta 均不存在。
- [ ] progress **89** → `✅`。

## 进度更新

完成后建议下一步 **90**。
