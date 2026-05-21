# 38 - 流式护栏与撤回事件

## 建议执行模型

- 模型：GPT-5.5
- Reasoning：high
- 原因：要在 optimistic streaming 下补撤回/替换语义，既要保留体验，也要守住出站护栏。

## 依赖

37

## 背景

真流式会降低首 token 延迟，但整段出站护栏会阻塞流式。PRD 决策：采用 optimistic streaming / incremental moderation / post-hoc moderation。

## 目标

- 对流式输出做句子级或窗口级检查。
- 发现违规时发送 `retract` 或 `replace` 事件。
- 高风险场景可降级到整段护栏。

## 范围

| 模块 | 变更 |
|------|------|
| `agent/src/gateway/chat.py` | SSE 支持 `retract`、`replace` |
| `agent/src/guardrails/outbound.py` | 增量检查 helper |
| `agent/tests/test_chat_sse.py` | 覆盖撤回/替换事件 |
| `front/` | 最小 demo 支持隐藏/替换已展示文本 |
| `README.md` | 同步 SSE 事件契约 |
| `docs/progress.md` | 本任务状态 |

## 事件建议

```json
{"type": "token", "content": "...", "segment_id": "seg-1"}
{"type": "retract", "segment_id": "seg-1", "reason": "outbound_guard"}
{"type": "replace", "segment_id": "seg-1", "content": "安全替换文本"}
{"type": "done"}
```

## 非范围

- 不引入复杂安全模型。
- 不保证所有违规 token 从未展示过。
- 不改 inbound guard。

## 测试方案

```bash
cd agent
uv run pytest tests/test_chat_sse.py tests/test_guardrails_outbound.py -v
```

## 完成标准

- [ ] 前端 demo 能处理 `retract` / `replace`。
- [ ] 出站违规时不会只静默失败。
- [ ] 高风险降级路径有测试。
- [ ] README 与 `docs/progress.md` 同步。

## 进度更新

`docs/progress.md` **38** → 实现完成后改为 `✅`。
