# 20 - KB Ingest API

## 依赖

02, 05, 11

## 目标

`POST /internal/kb/ingest`：按 `doc_id`+`version`，按 **doc_name** 删旧 chunk 再写入 Qdrant；分块 512–1024 token，overlap 10–15%。

## 范围

- `agent/src/rag/ingest.py`：分块、embedding、upsert、delete-by-doc_name
- `agent/src/gateway/ingest.py` 路由
- payload：`role_id`, `doc_id`, `doc_name`, `version`, `content`（或 `file_path` 内网路径）

## 非范围

- Admin UI
- 异步大文件队列（可同步简化）

## 实现要点

- 分块参数可配置 `CHUNK_SIZE_TOKENS`, `CHUNK_OVERLAP_RATIO`
- 失败时尽量不留半套旧+新（事务或先写新版本再删旧 version）

## 测试方案

```bash
cd agent
uv run pytest tests/test_kb_ingest.py -v
```

mock Qdrant：ingest 后 search 能命中；同 doc_name 再 ingest 旧 version 不可见。

## 完成标准

- 与根目录 README 的 RAG Ingest 与 KB API 契约一致

## 进度更新

`docs/progress.md` **20** → `✅`
