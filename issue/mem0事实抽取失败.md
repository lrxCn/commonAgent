# 背景
1. 存mem0用户画像时，是异步的，会先对用户吐出文字，然后在异步任务里执行信息存储。
2. 意图识别为fact_update后，会交给mem0存储用户画像。

# 问题
mem0使用infer=true做存储，但是Qwen/Qwen2.5-7B-Instruct未能提取出事实，导致store_empty,但是已经回复用户 "已收到，我会把这个信息作为你的偏好/事实参考。"

# 解决方案

**已落地（2026-05-25，任务 63-68）**：采用 Single Extraction Point + 双轨写入——Policy 通过的 `fact_update` 在控制面确定性 slot fill 为 `StructuredMemoryRecord`，post_turn 走 `store_structured_record(..., infer=False)`；其他回合仍走 `extract_and_store(..., infer=True)` 慢路径。详见 [docs/prd/agent-structured-memory-write.md](../docs/prd/agent-structured-memory-write.md) 与 [README.md](../README.md) 记忆写入章节。
