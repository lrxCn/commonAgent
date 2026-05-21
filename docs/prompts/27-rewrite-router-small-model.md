# 27 - Rewrite / RAG Router 小模型与超时保护

## 依赖

21, 26

## 背景与动机

LangSmith trace `019e443e-3848-71a0-a951-8bc023e847ee` 暴露出关键路径延迟问题：

| span | 模型 | 耗时 | 备注 |
|------|------|------|------|
| `rewrite -> ChatOpenAI` | `Pro/moonshotai/Kimi-K2.6` | 39.433s | token usage 异常偏大，含大量 reasoning tokens |
| `rag_router -> ChatOpenAI` | `Pro/moonshotai/Kimi-K2.6` | 17.082s | 小分类任务不应使用主力大模型 |
| `supervisor -> ChatOpenAI` | `Pro/moonshotai/Kimi-K2.6` | 6.957s | 主回复用大模型可接受 |

`rewrite` 和 `rag_router` 都是短 prompt、低创造性、结构化/半结构化任务。继续 fallback 到 `OPENAI_MODEL_NAME` 会让小任务被主力模型的排队、reasoning 或 provider 延迟拖慢。

后续 LangSmith trace 发现 `Qwen/Qwen2.5-7B-Instruct` 在 rewrite 中把「我出生于1997年」错误改成「我出生于111年」。因此 rewrite 不能只靠 prompt 约束：必须对个人/公司事实陈述直接跳过 LLM，并对数字篡改做输出校验回退。另一个 trace 显示 `rag_router` 对「我公司在天翔街188号」这类事实陈述进入 hybrid LLM 后 timeout；这类信息应作为记忆事实写入，不应查企业知识库，也不应调用 router LLM。

实测 SiliconFlow 候选（同一极短 rewrite prompt）：

| 模型 | 延迟 | 结果 |
|------|------|------|
| `Qwen/Qwen2.5-7B-Instruct` | 0.95s | 输出正常，推荐 |
| `THUDM/GLM-4-9B-0414` | 0.56s | 很快，但输出偏短，备选 |
| `Qwen/Qwen3.5-4B` | 1.02s | 本次输出为空，不稳 |
| `Qwen/Qwen3-8B` | 13.95s | reasoning tokens 多，不适合作为小任务默认 |

## 目标

- `rewrite` 和 `rag_router` 默认推荐使用快速小模型：`Qwen/Qwen2.5-7B-Instruct`。
- 给 `rewrite` / `rag_router` 的 ChatOpenAI 调用增加 `max_tokens` 上限，防止小任务输出失控：
  - rewrite：默认 `64`
  - rag_router：默认 `32`
- 增加请求 timeout 或等价保护；超时/异常时使用现有 fallback：
  - rewrite：回退原文
  - rag_router：保守返回需要 RAG
- LangSmith metadata 能看出本轮使用的模型、是否 fallback、prompt 长度、skip reason。
- rewrite 不得修改用户事实；个人/公司事实陈述应 passthrough，输出篡改原文数字时必须回退原文。
- rag_router 对个人/公司事实陈述直接 skip RAG；hybrid LLM 只处理规则不确定查询，timeout 默认 5 秒且不重试。

## 范围

| 模块 | 变更 |
|------|------|
| `agent/src/settings/config.py` | 增加小任务模型/输出上限/timeout 配置（或使用已有模型字段并补 max token/timeout 字段） |
| `agent/.env.example` | 写入推荐 `REWRITE_MODEL_NAME`、`RAG_ROUTER_MODEL_NAME`，以及新增上限/timeout 示例 |
| `agent/src/rag/rewrite.py` | `_create_chat_model` 使用小任务配置；设置 `max_tokens`、timeout；异常仍回退原文 |
| `agent/src/rag/router.py` | classifier model 设置 `max_tokens`、timeout；异常仍 conservative default `True` |
| `agent/src/observability/tracing.py` | rewrite/router metadata 补模型名、prompt 长度、fallback/skip 信息 |
| `agent/tests/test_rewrite.py` | 覆盖小模型配置、max_tokens/timeout 传参、异常 fallback |
| `agent/tests/test_rag_router.py` | 覆盖小模型配置、max_tokens/timeout 传参、异常 fallback |
| `agent/tests/test_settings.py` | 覆盖新增配置默认值与 env 解析 |
| 根目录 `README.md` | 同步小任务模型推荐与延迟保护说明 |
| `docs/progress.md` | 本任务状态 |

## 非范围

- 不修改 `OPENAI_MODEL_NAME` 主模型默认值。
- 不更换 Supervisor 主回复模型。
- 不调整 RAG 检索、rerank、mem0、summary 语义。
- 不把 rewrite 与 rag_router 合并为单次 LLM。
- 本地 `agent/.env` 只允许同步本任务的非密钥模型/上限/timeout 配置；不改真实 key，不提交 `.env`。

## 推荐配置

```env
# 小任务模型：低延迟 rewrite / router，不使用主力大模型
REWRITE_MODEL_NAME=Qwen/Qwen2.5-7B-Instruct
RAG_ROUTER_MODEL_NAME=Qwen/Qwen2.5-7B-Instruct

# 输出保护
REWRITE_MAX_TOKENS=64
RAG_ROUTER_MAX_TOKENS=32

# 超时保护（秒）
REWRITE_TIMEOUT_SECONDS=15
RAG_ROUTER_TIMEOUT_SECONDS=5
```

若 `Qwen/Qwen2.5-7B-Instruct` 当日 provider 不稳定，可手动试 `THUDM/GLM-4-9B-0414`，但要关注 rewrite 输出是否过短。

## 实现要点

### 1. Settings

建议新增字段：

```python
REWRITE_MAX_TOKENS: int = 64
REWRITE_TIMEOUT_SECONDS: float = 15
RAG_ROUTER_MAX_TOKENS: int = 32
RAG_ROUTER_TIMEOUT_SECONDS: float = 5
```

保留现有语义：

- `REWRITE_MODEL_NAME` 未设置时仍可 fallback 到 `OPENAI_MODEL_NAME`，但 `.env.example` 必须给出小模型推荐值。
- `RAG_ROUTER_MODEL_NAME` 未设置时仍可 fallback 到 `OPENAI_MODEL_NAME`，但 `.env.example` 必须给出小模型推荐值。

### 2. ChatOpenAI 参数

rewrite：

```python
ChatOpenAI(
    model=settings.REWRITE_MODEL_NAME or settings.OPENAI_MODEL_NAME,
    temperature=0,
    max_tokens=settings.REWRITE_MAX_TOKENS,
    timeout=settings.REWRITE_TIMEOUT_SECONDS,
)
```

rag_router：

```python
ChatOpenAI(
    model=settings.RAG_ROUTER_MODEL_NAME or settings.OPENAI_MODEL_NAME,
    temperature=0,
    max_tokens=settings.RAG_ROUTER_MAX_TOKENS,
    timeout=settings.RAG_ROUTER_TIMEOUT_SECONDS,
)
```

若当前 `langchain-openai` 参数名不支持 `timeout`，使用其支持的等价参数（如 `request_timeout`），并在测试中固定。rewrite/router 小任务不启用 ChatOpenAI 自动重试，避免关键路径被隐式重试拖慢。

### 3. Observability

metadata 至少包含：

| span | 字段 |
|------|------|
| rewrite | `rewrite.model_name`、`rewrite.prompt_len`、`rewrite_skipped`、`rewrite_skip_reason`、`rewrite.fallback` |
| rag_router | `rag_router.model_name`、`rag_router.prompt_len`、`rag_router.mode`、`rag_router.fallback` |

注意不要把完整 prompt 或 secrets 放入 metadata；长文本继续走截断/脱敏。

### 4. Fallback

- rewrite LLM 超时、异常、空输出：返回用户原文 trim。
- rewrite LLM 输出如篡改原文数字：返回用户原文 trim，并记录 `rewrite.fallback_reason=number_changed`。
- 个人/公司事实陈述（如生日、出生年份、姓名、职业、公司地址等）不需要消解指代时直接跳过 rewrite LLM。
- rag_router 识别个人/公司事实陈述时直接返回不需要 RAG，不调用 classifier LLM。
- rag_router LLM 超时、异常、JSON 解析失败：返回 `True`（保守走 RAG）。

## 测试方案

```bash
cd agent
uv run pytest tests/test_settings.py tests/test_rewrite.py tests/test_rag_router.py -v
uv run pytest tests/test_graph_invoke_mock.py -v
```

| 用例 | 期望 |
|------|------|
| Settings 默认 | max token / timeout 默认值正确；mock 默认仍以运行默认值为准 |
| env 覆盖 | `REWRITE_MAX_TOKENS`、`RAG_ROUTER_MAX_TOKENS`、timeout 可解析 |
| rewrite model 构造 | 使用 `REWRITE_MODEL_NAME`，设置 max tokens / timeout |
| router model 构造 | 使用 `RAG_ROUTER_MODEL_NAME`，设置 max tokens / timeout |
| rewrite 异常 | 回退原文 |
| rewrite 数字篡改 | 回退原文 |
| 个人事实陈述 | 跳过 rewrite LLM，`rewritten_query` 等于原文 |
| 公司地址事实陈述 | rewrite 跳过 LLM；router `rag_skipped=True` |
| router 异常 | conservative default = `need_rag=True` |
| tracing metadata | 能看到模型名、prompt 长度、fallback/skip 信息 |

## 手工验证

1. 本地 `agent/.env` 临时设置：

   ```env
   REWRITE_MODEL_NAME=Qwen/Qwen2.5-7B-Instruct
   RAG_ROUTER_MODEL_NAME=Qwen/Qwen2.5-7B-Instruct
   ```

2. 用 LangGraph Studio 或 Gateway 发起：

   ```text
   我是个前端程序员
   ```

3. LangSmith 验收：

   - `rewrite -> ChatOpenAI` 使用 `Qwen/Qwen2.5-7B-Instruct`。
   - `rag_router -> ChatOpenAI` 使用 `Qwen/Qwen2.5-7B-Instruct`，或规则直接跳过 LLM。
   - rewrite/router 小任务不再出现几十秒级耗时。
   - usage 不再出现异常巨大的 reasoning tokens。

## 完成标准

- [x] `.env.example` 写入小任务模型推荐值与输出/timeout 配置；本机 `.env` 已同步非密钥配置。
- [x] rewrite/router ChatOpenAI 有 max token 和 timeout 保护。
- [x] 异常 fallback 行为不变且有测试。
- [x] rewrite 对个人/公司事实陈述 passthrough；输出篡改数字时回退原文。
- [x] rag_router 对个人/公司事实陈述 skip RAG，不调用 classifier LLM。
- [x] LangSmith metadata 可定位模型与 fallback。
- [x] 上述 pytest 通过。
- [x] 根目录 README 与 `docs/progress.md` 同步。

## 进度更新

`docs/progress.md` **27** → 实现完成后改为 `✅`。
