# 32 - rewrite/router 按 turn_type 收敛

## 依赖

28, 29, 30, 31

## 背景

当前 rewrite/router 内部仍有各自规则。引入 turn type 后，应让两者消费统一分类结果，减少重复正则和无效小模型调用。

## 目标

- rewrite 默认不调用 LLM，只有 `ambiguous` 或明确历史依赖才调用。
- router 对 `fact_update`、`chitchat`、`client_action` 直接 skip。
- `knowledge_query` 直接 RAG，不走 router LLM。
- router 小模型仅用于规则不确定场景。

## 范围

| 模块 | 变更 |
|------|------|
| `agent/src/rag/rewrite.py` | 接收/使用 turn_type；收紧调用条件 |
| `agent/src/rag/router.py` | 接收/使用 turn_type；减少内部重复判断 |
| `agent/src/graph/nodes.py` | 将 turn_type 传入 rewrite/router payload |
| `agent/tests/test_rewrite.py` | 覆盖 turn_type 下的调用/跳过 |
| `agent/tests/test_rag_router.py` | 覆盖 turn_type 下的调用/跳过 |
| `README.md` | 同步策略收敛 |
| `docs/progress.md` | 本任务状态 |

## 非范围

- 不删除所有旧规则，允许保留作为 fallback。
- 不改 fast path 已完成行为。
- 不改 deepagents。

## 测试方案

```bash
cd agent
uv run pytest tests/test_rewrite.py tests/test_rag_router.py tests/test_path_contract.py -v
```

## 完成标准

- [ ] `fact_update`、`chitchat` 不调用 rewrite/router 小模型。
- [ ] `knowledge_query` 不调用 router 小模型，直接 retrieve。
- [ ] `ambiguous` 可调用 rewrite。
- [ ] Path Contract 能发现意外调用。
- [ ] README 与 `docs/progress.md` 同步。

## 进度更新

`docs/progress.md` **32** → 实现完成后改为 `✅`。

