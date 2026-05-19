# 16 - client_actions 输出契约

## 依赖

04, 13

## 目标

当用户意图为外部工具时，Supervisor 产出结构化 **`client_actions`**，**不执行、不等待**；本轮回话结束。

## 范围

- 扩展 `ChatResponse` / assistant 消息 metadata
- `agent/src/graph/client_actions.py`：从 LLM 输出解析 JSON；校验 tool 在 `context.tools` 白名单内
- 图分支：有 client_actions 时 **不** 再走出站文本流式（或仅短确认语，按产品：建议仅 JSON）
- Checkpoint 存 assistant + metadata，**无** ToolMessage

## 非范围

- Front 执行
- 服务端工具第二轮回

## 实现要点

- 示例：`jumpPage` + `requires_approval`
- ToolSubAgent **不**代执行外部工具

## 测试方案

```bash
cd agent
uv run pytest tests/test_client_actions.py -v
```

用例：LLM 返回 client_actions JSON → 校验通过；tool 不在白名单 → 拒绝；解析失败 → 错误码。

## 完成标准

- 与 architecture §7 示例一致
- Gateway stub 可返回带 client_actions 的 JSON

## 进度更新

`docs/progress.md` **16** → `✅`
