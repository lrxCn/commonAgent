# 120 - 火山 SAUC 修复：PCM 首包与 audio-only header（ser=0）

## 建议执行模型

- 模型：较快编码模型即可
- Reasoning：low
- 原因：协议位修改已有实验 A 证据，改 `protocol.py` + 测试即可。

## 新窗口执行规则

1. 先读 handoff、[官方 Message flow](https://www.volcengine.com/docs/6561/1354869?lang=zh)、`docs/progress.md` 与本任务卡。
2. 依赖 **119** 已完成。
3. 只改 `protocol.py` 与相关测试；不改 Front。
4. 测试通过后 progress **120** → `✅`；git commit。

## 依赖

**119**

## 背景

联调证实 **45000151（音频格式不正确）** 因 audio-only 帧误用 JSON serialization；修复后 remote 轨出现 `asr.partial/final`（见 handoff §2.2、§6）。

## 目标

- full client request：`audio.format` = **`pcm`**（`codec: raw`，16k/mono/16bit 不变）。
- audio-only request：header serialization = **`none`（0x0）**，compression 仍为 gzip。
- 单元测试锁定 `ser=0` 与 `format==pcm`。

## 范围

| 区域 | 变更 |
|------|------|
| `back/src/services/volc_asr/protocol.py` | `SERIALIZATION_NONE`；`build_audio_only_request`；`build_full_client_payload` |
| `back/tests/test_volc_asr_protocol.py` | 断言 pcm + audio-only ser=0 |

## 实施步骤

1. 增加 `SERIALIZATION_NONE = 0b0000`。
2. `build_full_client_payload` → `format: "pcm"`。
3. `build_audio_only_request` → `_header_bytes(..., serialization=SERIALIZATION_NONE)`。
4. 可选：`describe_frame_header()` 仅供测试断言，勿引入运行时 debug 日志。

## 验证方案

```bash
cd back && uv run pytest tests/test_volc_asr_protocol.py tests/test_asr_ws.py -v
```

期望：audio 首帧 `frame[2] >> 4 == 0`。

## 非范围

- 修改 `back/demo/sauc_python`（handoff 明确勿改 demo 行为为本任务）
- asr_proxy 业务逻辑（**121**）

## 完成标准

- [ ] 协议与官方 Message flow 一致。
- [ ] 测试覆盖 pcm + ser=0。
- [ ] pytest 绿；progress **120** ✅；git commit。

## 进度更新

建议下一步 **121**。
