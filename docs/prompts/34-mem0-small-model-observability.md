# 34 - mem0 小模型配置与写入可观测性

## 依赖

17, 24, 28, 29

## 背景

mem0 写入 infer 当前使用主模型配置，可能造成后台成本和队列压力。fact_update 快速确认后，mem0 写入失败也必须可追踪。

## 目标

- mem0 写入使用专用小模型配置。
- mem0 写入失败有结构化日志、trace metadata、失败计数入口。
- 不阻塞用户本轮响应。

## 范围

| 模块 | 变更 |
|------|------|
| `agent/src/settings/config.py` | 新增 `MEM0_LLM_MODEL_NAME`、timeout/max token 等配置 |
| `agent/.env.example` | 新增 mem0 小模型示例 |
| `agent/src/memory/mem0_client.py` | mem0 config 使用专用模型 |
| `agent/src/memory/mem0_write.py` / `post_turn.py` | 结构化失败 reason、metadata |
| `agent/tests/` | 覆盖配置、成功/失败、mock |
| `README.md` | 同步 mem0 成本控制 |
| `docs/progress.md` | 本任务状态 |

## 非范围

- 不实现重试队列。
- 不实现 memory_profile schema。
- 不改 mem0 cloud 约束。

## 测试方案

```bash
cd agent
uv run pytest tests/test_settings.py tests/test_mem0_read.py tests/test_mem0_write.py tests/test_post_turn_graph.py -v
```

## 完成标准

- [ ] mem0 写入不默认使用 `OPENAI_MODEL_NAME`。
- [ ] `.env.example` 有小模型配置。
- [ ] 写入失败可通过日志/metadata 定位。
- [ ] 不阻塞 chat 主链路。
- [ ] README 与 `docs/progress.md` 同步。

## 进度更新

`docs/progress.md` **34** → 实现完成后改为 `✅`。

