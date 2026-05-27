# 119 - 火山 SAUC 修复：新控制台鉴权与 env 契约

## 建议执行模型

- 模型：较快编码模型即可
- Reasoning：low
- 原因：对照已验证的联调结论改 `client.py` 与 env 注释，范围窄。

## 新窗口执行规则

1. 先读 `AGENTS.md`、`README.md`、`docs/progress.md`、[volc-asr-fix-handoff.md](../prd/volc-asr-fix-handoff.md) 与本任务卡。
2. 核对依赖无（本批次首任务）。
3. 只实现本任务范围；**不**改 `protocol.py`（任务 **120**）。
4. 运行测试计划。
5. 更新 progress **119** → `✅`。
6. 自动 git commit；不 push。

## 依赖

无（修复批次 **119–123** 首任务；原 **116–117** 已合并但存在回归，见 handoff）。

## 背景

[volc-asr-fix-handoff.md](../prd/volc-asr-fix-handoff.md) 已证实：旧版 `X-Api-Access-Key` + `X-Api-App-Key` 对新控制台 **401**；新鉴权为 `X-Api-Key` + `X-Api-Sequence: -1`（[官方文档](https://www.volcengine.com/docs/6561/1354869?lang=zh)「新版本控制台」）。

## 目标

- `VolcAsrClient._auth_headers()` 仅发送新控制台头。
- `VOLC_ASR_ACCESS_KEY` 语义文档化为 **X-Api-Key**；移除或废弃 `VOLC_ASR_APP_KEY` 在运行路径中的使用（可保留 settings 字段但不再发送旧头）。
- `.env.example` 注释与默认 `VOLC_ASR_RESOURCE_ID` 对齐 ASR 2.0 示例（`volc.seedasr.sauc.duration`），并说明 1.0 取值。

## 范围

| 区域 | 变更 |
|------|------|
| `back/src/services/volc_asr/client.py` | `_auth_headers()` → `X-Api-Key`、`X-Api-Resource-Id`、`X-Api-Request-Id`、`X-Api-Sequence: -1` |
| `back/src/settings/config.py` | `VOLC_ASR_ACCESS_KEY` / `VOLC_ASR_APP_KEY` 字段描述 |
| `back/.env.example` | 注释 + 默认 resource 示例 |
| `back/tests/` | mock 上游或 client 测试断言新 header（若无则增最小用例） |

## 实施步骤

1. 修改 `client.py` 鉴权头；**不要**实现旧版双 Key 切换。
2. 同步 `config.py` 与 `.env.example` 三者契约（AGENTS.md 规则）。
3. 更新/新增测试：连接 mock 时 header 含 `X-Api-Key`、无 `X-Api-Access-Key`。

## 验证方案

```bash
cd back && uv run pytest tests/test_volc_asr_protocol.py tests/test_asr_ws.py -v
```

## 非范围

- `protocol.py` pcm/ser=0（**120**）
- Front `asr.ts`（**122**）
- 联调时间线 debug 日志

## 完成标准

- [ ] 新鉴权头与 handoff 一致。
- [ ] env 三文件契约同步。
- [ ] 上述 pytest 通过。
- [ ] progress **119** ✅；git commit。

## 进度更新

`docs/progress.md` **119** → `✅`；建议下一步 **120**。
