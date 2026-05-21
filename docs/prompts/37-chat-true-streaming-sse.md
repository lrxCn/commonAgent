# 37 - Chat 真流式 SSE

## 建议执行模型

- 模型：GPT-5.5
- Reasoning：high
- 原因：涉及 Gateway、图调用和 SSE 时序，容易出现首 token、done、client_actions 顺序问题。

## 依赖

18, 33

## 背景

当前 SSE 是 graph 完整执行后切块，不是真首 token 流式。需要使用 LangGraph/model streaming，将文本边生成边转发。

## 目标

- 文本回复支持真流式 token。
- `client_actions` 继续返回结构化 JSON 或明确事件，不混入自然语言 token。
- 保持 Front -> Back -> Agent 边界。

## 范围

| 模块 | 变更 |
|------|------|
| `agent/src/gateway/chat.py` | 新增 streaming invoke 路径 |
| `agent/src/gateway/app.py` | SSE endpoint 使用真流式 |
| `agent/src/graph/supervisor.py` | 暴露可流式调用能力 |
| `agent/tests/test_chat_sse.py` | 覆盖 token 顺序、done、client_actions |
| `back/` | 如代理需要，更新转发测试 |
| `README.md` | 同步真流式契约 |
| `docs/progress.md` | 本任务状态 |

## SSE 事件

第一期至少支持：

```text
token
done
error
```

`retract` / `replace` 留给任务 38。

## 非范围

- 不实现流式出站护栏。
- 不改前端复杂 UI。
- 不改 client_actions 执行语义。

## 测试方案

```bash
cd agent
uv run pytest tests/test_chat_sse.py tests/test_graph_invoke_mock.py -v
cd ../back
uv run pytest tests/test_back_forward.py -v
```

## 完成标准

- [ ] 首个 token 不等待完整 graph 文本生成后才发。
- [ ] `done` 正确结束。
- [ ] client_actions 不被拆成普通文本 token。
- [ ] README 与 `docs/progress.md` 同步。

## 进度更新

`docs/progress.md` **37** → 实现完成后改为 `✅`。
