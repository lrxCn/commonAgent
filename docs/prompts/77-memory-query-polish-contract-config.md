# 77 - memory_query 润色 Phase 1：契约、配置与小模型客户端

## 建议执行模型

- 模型：GPT-5.5
- Reasoning：high
- 原因：本任务新增 LLM 用途、环境变量契约和输出校验，必须防止小模型获得事实决策权，并同步 settings/env 三方契约。

## 新窗口执行规则

1. 先读根目录 `AGENTS.md`、`README.md`、`docs/progress.md` 和本任务卡。
2. 阅读 PRD：[agent-memory-query-polish.md](../prd/agent-memory-query-polish.md)。
3. 核对任务 76 已完成；未完成则停止。
4. 对比当前模型和 reasoning 与本节建议；如果不一致或未知，先告诉用户建议配置并等待确认，除非用户明确要求继续。
5. 只实现本任务范围，不接主图。
6. 按本任务测试计划验证。
7. 测试通过后更新 `docs/progress.md`；不要自动 push，除非用户明确要求。

## 依赖

76

## 背景

小模型润色必须被建模为独立用途：它只能消费 `MemoryQueryResult` 的确定性草稿和 evidence，不能重新读取记忆或推断事实。本任务先建立 contract、配置和纯函数，为任务 78 接 graph 做准备。

## 目标

- 新增 memory query polish contract。
- 新增 `ModelUseCase.MEMORY_QUERY_POLISH` 或等价用途。
- 新增 settings/env：开关、模型名、max tokens、timeout。
- 新增小模型调用函数和输出校验。
- 小模型失败或校验失败时返回 deterministic draft。

## 范围

| 模块 | 变更 |
|------|------|
| `agent/src/contracts/llm.py` | 新增 memory query polish 模型用途 |
| `agent/src/infrastructure/llm/policy.py` | 增加 small model policy |
| `agent/src/settings/config.py` | 新增 `MEMORY_QUERY_POLISH_*` 配置 |
| `agent/.env.example` | 新增配置注释和示例 |
| `agent/.env` | 同步本机配置键 |
| `agent/src/memory/query_polish.py` | 新增 polish 输入构造、LLM 调用、校验和 fallback |
| `agent/tests/test_memory_query_polish.py` | 覆盖配置、prompt 输入、输出校验、fallback |
| `agent/tests/test_settings.py` | 环境契约测试应继续通过 |
| `docs/progress.md` | 本任务完成后更新状态 |

## 配置建议

```text
MEMORY_QUERY_POLISH_USE_LLM=false
MEMORY_QUERY_POLISH_MODEL_NAME=
MEMORY_QUERY_POLISH_MAX_TOKENS=80
MEMORY_QUERY_POLISH_TIMEOUT_SECONDS=5
```

默认关闭，避免无意增加线上延迟。

## 输出校验要求

- 有 evidence 时，所有 `value` 必须保留在最终回复中。
- 缺失记忆时，不得输出肯定身份事实。
- 输出为空、超长、异常、超时、schema 错误时回退 deterministic draft。
- 输出校验失败要返回结构化 fallback reason。

## 验证方案

```bash
cd agent
uv run pytest tests/test_memory_query_polish.py tests/test_settings.py -v
uv run ruff check src tests
```

## 非范围

- 不改 graph 拓扑。
- 不改 `memory_query_reply_node`。
- 不更新 README 当前运行契约。

## 完成标准

- [ ] contract 和纯函数测试覆盖成功、失败、校验失败、缺失记忆。
- [ ] LLM Gateway 策略可观测模型用途。
- [ ] env 三方契约同步且 `test_env_files_match_settings_contract` 通过。
- [ ] `docs/progress.md` 更新 77 状态。

## 进度更新

`docs/progress.md` **77** → 实现完成后改为 `✅`；当前建议下一步改为 78。
