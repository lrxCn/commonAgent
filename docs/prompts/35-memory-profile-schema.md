# 35 - memory_profile 类别化记忆视图

## 依赖

34

## 背景

mem0 自由文本事实容易重复、冲突、难删除。PRD 建议短期保留 mem0 原始事实，同时新增应用侧 `memory_profile` 归一化视图。

## 目标

- 建立第一版类别化 schema。
- 从 mem0 facts 归一化高频稳定字段。
- system 注入优先使用类别化事实，减少重复自由文本。

## 范围

| 模块 | 变更 |
|------|------|
| `agent/src/memory/profile.py` | 定义 `MemoryProfile`、归一化规则 |
| `agent/src/memory/assembly.py` | 注入 profile + 少量相关自由文本 |
| `agent/src/memory/prompts/` | 如需小模型抽取，新增 prompt |
| `agent/tests/` | 覆盖 name/city/job/company.address/preference |
| `README.md` | 同步类别化记忆策略 |
| `docs/progress.md` | 本任务状态 |

## 第一批字段

```text
profile.name
profile.birth_year
profile.city
profile.job
company.address
preference.answer_style
```

## 非范围

- 不迁移历史 Qdrant 数据。
- 不做用户删除记忆 UI。
- 不引入新数据库表，除非现有实现确实无法表达。

## 测试方案

```bash
cd agent
uv run pytest tests/test_memory_profile.py tests/test_context_assembly.py -v
```

## 完成标准

- [ ] 同类事实去重，保留最新/最明确值。
- [ ] system prompt 不重复注入同类自由文本。
- [ ] 旧 mem0 facts 仍兼容。
- [ ] README 与 `docs/progress.md` 同步。

## 进度更新

`docs/progress.md` **35** → 实现完成后改为 `✅`。

