# 31 - chitchat 轻量执行器

## 依赖

28, 29

## 背景

寒暄、感谢、简单确认不应进入主模型和 deepagents。PRD 决策：`chitchat` 走模板或小模型。

## 目标

- `chitchat` 跳过 rewrite、RAG、deepagents。
- 低风险场景用模板回复；需要自然一点的场景可配置小模型。
- Path Contract 能区分模板路径与小模型路径。

## 范围

| 模块 | 变更 |
|------|------|
| `agent/src/graph/nodes.py` | 增加 chitchat 路由与轻量回复节点 |
| `agent/src/settings/config.py` | 可选 `CHITCHAT_MODEL_NAME`、`CHITCHAT_USE_LLM`、timeout/max token |
| `agent/.env.example` | 新增 chitchat 小模型配置示例 |
| `agent/src/observability/tracing.py` | 记录 `executor=template_executor/small_chat_executor` |
| `agent/tests/` | 覆盖模板、小模型开关、路径契约 |
| `README.md` | 同步 chitchat 轻量执行器 |
| `docs/progress.md` | 本任务状态 |

## 非范围

- 不做复杂 general_chat。
- 不改 Supervisor。
- 不改流式。

## 测试方案

```bash
cd agent
uv run pytest tests/test_chitchat_executor.py tests/test_settings.py tests/test_graph_invoke_mock.py -v
```

## 完成标准

- [ ] 默认 chitchat 不调用主模型。
- [ ] 配置可切换模板/小模型。
- [ ] 不触发 RAG。
- [ ] Path Contract pass。
- [ ] README 与 `docs/progress.md` 同步。

## 进度更新

`docs/progress.md` **31** → 实现完成后改为 `✅`。

