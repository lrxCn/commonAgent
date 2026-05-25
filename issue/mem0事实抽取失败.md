# 背景
1. 存用户画像时，是异步的，会先对用户吐出文字，然后在异步任务里执行信息存储。
2. 意图识别为 fact_update 后，会交给存储面写入用户记忆。

# 问题
早期 mem0 使用 infer=true 做存储，Qwen/Qwen2.5-7B-Instruct 未能提取出事实，导致 stored_empty，但已经回复用户「已收到，我会把这个信息作为你的偏好/事实参考。」

# 解决方案

**已落地（2026-05-25）**：

1. **Structured Write（任务 63-68）**：Policy 通过的 `fact_update` 在控制面确定性 slot fill 为 `StructuredMemoryRecord`，post_turn 走 `store_structured_record()` → LangGraph Store profile put，不再依赖概率性二次抽取。
2. **LangMem 迁移（任务 69-74）**：用户记忆栈从 mem0+Qdrant 迁至 **LangGraph Postgres Store + langmem**；inferred 慢路径经 `MEMORY_EXTRACT` 小模型 + `create_memory_store_manager`；`user_memories` state 字段与 README/maps 已收口。

详见 [docs/prd/agent-structured-memory-write.md](./agent-structured-memory-write.md)、[docs/prd/agent-langmem-migration.md](./agent-langmem-migration.md) 与 [README.md](../README.md) 记忆章节。
