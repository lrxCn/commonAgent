# 103 - jumpPage：Agent catalog 对齐与 pageA 迁移

## 建议执行模型

- 模型：GPT-5 或同档强编码模型
- Reasoning：medium
- 原因：跨 executors、router、eval seed、多份测试，需保持 intent/action 路径行为一致。

## 新窗口执行规则

1. 先读 `AGENTS.md`、`README.md`、`docs/progress.md`、PRD 与本任务卡。
2. 核对 **102** 已完成（Back tools enum 已落地）。
3. 只改 Agent 侧；Front 执行留 **104**。
4. 测试通过后更新 progress 并 commit。

## 依赖

102

## 背景

Agent 测试与 eval 仍使用虚构 `pageA`；`build_simple_client_action()` 仅支持 regex 抽 `pageX` / 路径，未对齐 PRD slug catalog。Back 已在 **102** 注入 enum，本任务让 Agent 规则路径与评测种子与 catalog 一致。

## 目标

- `build_simple_client_action()` 支持 PRD slug：识别 catalog slug、中文菜单关键词（如「学生管理」→ `students`）、`/app/...` path → slug 反向映射。
- 可选：`is_pure_client_tool_intent()` 将「学生管理」等菜单词纳入纯导航意图（与 RAG 区分）。
- 将 eval / 测试中面向 **演示跳转** 的 `pageA` 改为 `students` / `home` / `admin-kb` 等真实 slug；保留 schema 契约测试里对 `pageA` 的 **纯结构** 用例若与 catalog 无关可保留，但 path contract / executor / intent seed 应迁移。
- **不**在 Agent 内 duplicate 完整页面列表文件（仍以 Back 注入 ToolSpec 为准）。

## 范围

| 模块 | 变更 |
|------|------|
| `agent/src/graph/executors.py` | slug / 中文 / path 抽取 |
| `agent/src/rag/router.py` | 可选：导航菜单词 |
| `agent/evals/*.json` | intent_seed、seed 等话术与 expected |
| `agent/tests/` | `test_executor_router.py`、`test_path_contract.py`、`test_rag_router.py`、`test_intent_*` 等涉及 pageA 的跳转用例 |

## 实施步骤

1. 在 `executors.py` 增加 slug 常量表（与 PRD 一致，仅用于规则抽取，非 prompt 权威源）。
2. 扩展 `_extract_page_arg` 或等价逻辑：优先 slug enum，再中文别名，再 legacy path。
3. 更新 intent/eval seed：「打开 pageA」→「打开学生管理」等。
4. 跑相关 pytest；确认 ACTION 快捷路径与 deepagents JSON 路径仍通过白名单校验。

## 验证方案

```bash
cd agent && uv run pytest \
  tests/test_executor_router.py \
  tests/test_client_actions.py \
  tests/test_path_contract.py \
  tests/test_rag_router.py \
  tests/test_intent_rules.py \
  tests/test_intent_eval_seed.py \
  -v
```

若 LLM 集成测试不可用，上述 unit 通过即可。

## 非范围

- Back `tools.demo.json`（**102** 已完成）
- Front `router.push`（**104**）
- README / maps（**105**）
- 新增 LangChain 工具注册

## 完成标准

- [ ] 简单导航句「打开学生管理」经 ACTION 路径产出 `page: "students"`（tools 含 jumpPage）。
- [ ] 核心 eval seed 无 `pageA` 作为期望跳转目标（结构测试除外若合理）。
- [ ] 上述 pytest 全绿。
- [ ] progress **103** → `✅`。
- [ ] git commit。

## 进度更新

`docs/progress.md` **103** → `✅`；建议下一步 **104**。
