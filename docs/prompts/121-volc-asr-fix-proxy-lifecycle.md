# 121 - 火山 SAUC 修复：asr_proxy 上游响应与挂断清理

## 建议执行模型

- 模型：较快编码模型即可
- Reasoning：medium
- 原因：异步会话生命周期与错误传播，需理清 stop/cleanup 边界。

## 新窗口执行规则

1. 先读 handoff §2.4、§7，`asr_proxy.py`、`asr_routes.py` 与本任务卡。
2. 依赖 **119**、**120**。
3. 不添加 `[ASR-TIMELINE]` 级联调日志；可用标准 `logger` 记录 upstream code 与异常类型。
4. 测试 + progress **121** ✅；git commit。

## 依赖

**119**, **120**

## 背景

- `send_full_request()` 返回值 **未检查** `code`。
- 从未收到 PCM 的 track 上游空等 → **45000081**；挂断时误报 UI error（handoff §2.4、§7）。
- 实验 A 中 **45000151** 已由 **120** 解决；本任务处理 proxy 层健壮性。

## 目标

- `start()` 后检查 `full_request` 响应 `code`，非 0 时 `asr.error` + cleanup。
- `connect`/`send_full_request` 异常记录 **类型与 message**（不打印密钥）。
- `stop`/session 清理：对 **从未 append_audio** 的 track，避免无意义 upstream 等待；挂断时 **不向 Front 抛** 可忽略的 `45000081`（或降为 debug）。
- 保持现有 `test_asr_ws.py` 行为兼容。

## 范围

| 区域 | 变更 |
|------|------|
| `back/src/services/asr_proxy.py` | 响应检查、cleanup、错误过滤 |
| `back/tests/test_asr_ws.py` | 必要时增补 mock 用例 |

## 实施步骤

1. 在 `AsrTrackSession.start` 处理 `full_response.code != 0`。
2. `except Exception` 分支 `logger.warning/exception` 含 `error_type`。
3. 跟踪「是否已收到 browser PCM」；未激活 track 在 `stop`/`unregister` 时静默关闭上游。
4. `_emit_response` 对挂断阶段已知超时码可选不转发 UI（需注释说明）。

## 验证方案

```bash
cd back && uv run pytest tests/test_asr_ws.py tests/test_volc_asr_protocol.py -v
```

## 非范围

- Front 延迟 start（**122**）
- 抓取 `X-Tt-Logid`（可留 TODO，非本任务必须）

## 完成标准

- [ ] full_request 失败可观测且不挂死 WS。
- [ ] 挂断不再稳定出现误导性 `asr.error` toast（在 mock/手工说明中验证）。
- [ ] pytest 绿；progress **121** ✅；git commit。

## 进度更新

建议下一步 **122**。
