# 51 - 控制面 Phase 2：LLM Structured Classifier 与冲突校验

## 建议执行模型

- 模型：GPT-5.5
- Reasoning：high
- 原因：本任务引入小模型结构化分类器和模型用途配置，必须遵守 LLM Gateway 与环境变量契约，同时确保模型输出不能直接拥有执行权。

## 依赖

50

## 背景

确定性规则只应处理高置信场景。对低置信或信号冲突的输入，需要小模型输出结构化 `IntentDecision` 候选，但最终能否执行必须由 Policy Gate 决定。

本任务实现 classifier 能力和冲突校验，但不接入 graph 执行路径。

## 目标

- 新增 `ModelUseCase.INTENT_CLASSIFIER`，统一通过 LLM Gateway 调用。
- 新增结构化 intent classifier，输出 Pydantic/JSON schema 校验后的 `IntentDecision` 候选。
- 新增 conflict check，识别规则与模型、信号与 route 的冲突。
- 对 schema invalid、timeout、provider error 提供安全 fallback。
- 不让 classifier 直接决定 fast path 或工具执行。

## 范围

| 模块 | 变更 |
|------|------|
| `agent/src/contracts/llm.py` | 新增 `ModelUseCase.INTENT_CLASSIFIER` |
| `agent/src/settings/config.py` | 如新增模型名、timeout、max token 配置，更新 Settings |
| `agent/.env.example` | 同步新增环境变量，示例值必须脱敏 |
| `agent/.env` | 同步本地环境变量，不提交真实秘密 |
| `agent/src/infrastructure/llm/gateway.py` | 接入 intent classifier 用途 |
| `agent/src/intent/classifier.py` | 小模型 structured output 分类器 |
| `agent/src/intent/conflicts.py` | 冲突检测和安全降级原因 |
| `agent/tests/test_intent_classifier.py` | mock LLM 覆盖结构化输出、非法 schema、timeout fallback |
| `agent/tests/test_settings.py` | 环境契约同步测试 |
| `docs/progress.md` | 本任务状态 |

## 环境契约要求

如果新增环境变量，必须同步：

- `agent/src/settings/config.py`
- `agent/.env.example`
- `agent/.env`

并运行：

```bash
cd agent
uv run pytest tests/test_settings.py -v
```

## classifier 约束

- 只在 deterministic rules 低置信或 conflict 时被调用。
- 输出必须通过 schema 校验。
- 输出必须包含 `confidence`、`risk`、`reasons`、`evidence`。
- 输出不能直接触发 memory write、client action 或 high-risk tool。
- schema invalid 时最多 repair 一次；仍失败则返回低置信 `general_chat` 或 `clarify` 候选。

## 非范围

- 不接管 graph 运行路径。
- 不改变 fast path。
- 不实现 Policy Gate。
- 不新增 memory executor。
- 不新增 HITL。
- 不更新 README 当前运行契约。

## 测试方案

```bash
cd agent
uv run pytest tests/test_settings.py tests/test_intent_classifier.py tests/test_intent_rules.py -v
uv run pytest tests/test_llm_gateway.py tests/test_contracts.py -v
uv run ruff check src tests
```

如果本地无真实 LLM，只运行 mock 覆盖，并在结果中说明 live path 未跑。

## 完成标准

- [ ] `ModelUseCase.INTENT_CLASSIFIER` 通过 LLM Gateway 统一配置。
- [ ] classifier 使用结构化输出，不解析自由文本。
- [ ] schema invalid / timeout / provider error 有安全 fallback。
- [ ] conflict check 能识别“疑问词 + memory_write”等高风险冲突。
- [ ] 环境契约三件套同步并通过 `test_settings.py`。
- [ ] 本任务不改变 graph 行为。
- [ ] `docs/progress.md` 同步。

## 进度更新

`docs/progress.md` **51** → 实现完成后改为 `✅`。
