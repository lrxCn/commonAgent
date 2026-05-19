# 07 - mem0 读取

## 依赖

02, 04

## 目标

对话开始时按 `user_id` 从 **mem0 + Qdrant** 拉取用户偏好，供后续注入 system。

## 范围

- `agent/src/memory/mem0_client.py`：`fetch_user_memories(user_id) -> list[str]`
- 无 mem0 服务时：可配置 `MEM0_MOCK=true` 返回空列表
- 格式化：`format_mem0_for_system(memories) -> str`

## 非范围

- 写入（任务 17）

## 实现要点

- 提取式事实语义；不存整段对话
- 与 checkpoint 读取 **可并行**（为任务 12/13 预留 async 接口）

## 测试方案

```bash
cd agent
uv run pytest tests/test_mem0_read.py -v
```

mock mem0 API：有记忆时返回列表；无 user_id 抛错。

## 完成标准

- 接口稳定，供 context 组装调用
- mock 模式可在 CI 跑通

## 进度更新

`docs/progress.md` **07** → `✅`
