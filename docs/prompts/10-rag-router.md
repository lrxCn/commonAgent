# 10 - RAG 路由

## 依赖

04, 09

## 目标

混合路由判断本轮 **是否执行 RAG**：规则优先，不确定时小模型分类。

## 范围

- `agent/src/rag/router.py`：`should_retrieve(message, rewritten_query, tools_context) -> bool`
- 规则：闲聊、纯 client tool 意图（如「跳转 pageX」且无知识问句）→ skip
- `RAG_ROUTER_MODE=rules|hybrid`

## 非范围

- Qdrant 检索实现

## 实现要点

- skip 时 state `rag_skipped=True`，下游不查库
- hybrid 时 LLM 输出 JSON `{"need_rag": true/false}`

## 测试方案

```bash
cd agent
uv run pytest tests/test_rag_router.py -v
```

表驱动：`你好` → false；`报销制度是什么` → true；`打开 pageA` + tools 含 jumpPage → false。

## 完成标准

- 规则路径无外部依赖即可测
- 与 architecture §6.1 一致

## 进度更新

`docs/progress.md` **10** → `✅`
