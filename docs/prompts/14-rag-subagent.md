# 14 - RagSubAgent 二查

## 依赖

11, 13

## 目标

Supervisor 判定主链路 `rag_chunks` 不足时，委派 **RagSubAgent** 做第二次检索；合并去重后写回 state。

## 范围

- `agent/src/graph/rag_subagent.py`
- 委派条件（第一期）：规则——如主检索结果为空或最高分 < 阈值（阈值可配置，默认 0.3）
- 二查可用更大 top_k 或不同 prompt；**不**重复第三次

## 非范围

- 分数阈值产品化调优（记 todo）
- 同 thread 检索缓存

## 实现要点

- 复用 `retrieve()`，标记 `second_pass=True` 便于 trace
- Supervisor prompt 说明何时委派

## 测试方案

```bash
cd agent
uv run pytest tests/test_rag_subagent.py -v
```

mock 空 chunks → 触发二查；有高质量 chunk → 不触发。

## 完成标准

- 图边条件可测
- 合并后 `rag_chunks` 条数 ≤ 上限

## 进度更新

`docs/progress.md` **14** → `✅`
