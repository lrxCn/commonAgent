# 04 - 请求 Context 模型

## 依赖

02

## 目标

定义每轮请求的 **context** 与 chat body Pydantic 模型；`user_id`、`role_id`、`tools[]` 不进 checkpoint state。

## 范围

- `agent/src/gateway/schemas.py`
  - `ToolSpec`: name, description, parameters (JSON Schema dict), requires_approval
  - `RequestContext`: user_id, role_id, tools
  - `ChatRequest`: thread_id, message, context
  - `ClientAction`, `ChatResponse`（含可选 client_actions）

## 非范围

- HTTP 路由

## 实现要点

- `tools` 默认 `[]`
- 校验 `thread_id` 非空字符串
- 与根目录 [README.md](../../README.md) 的 API 契约一致

## 测试方案

```bash
cd agent
uv run pytest tests/test_schemas.py -v
```

用例：合法 payload 解析；缺 context.role_id 失败；tool 含 requires_approval。

## 完成标准

- JSON 样例可 `model_validate`
- 导出 OpenAPI 友好字段名

## 进度更新

`docs/progress.md` **04** → `✅`
