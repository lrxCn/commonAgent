# 火山 SAUC 通话字幕 — 关键修复交接文档

> **状态**：2026-05-27 联调结论；仓库 `master` 上 ASR 实现（任务 116–117）仍含下列缺陷。  
> **执行任务卡**：[119](../prompts/119-volc-asr-fix-auth-env.md) → [120](../prompts/120-volc-asr-fix-protocol-pcm.md) → [121](../prompts/121-volc-asr-fix-proxy-lifecycle.md) → [122](../prompts/122-volc-asr-fix-front-track-start.md) → [123](../prompts/123-volc-asr-fix-docs-final.md)（进度见 [progress.md](../progress.md)）。  
> **官方文档**：[大模型流式语音识别 API](https://www.volcengine.com/docs/6561/1354869?lang=zh)  
> **勿作协议真相**：`back/demo/sauc_python/sauc_websocket_demo.py`（旧控制台鉴权、默认 nostream、wav 整文件分包等问题）

---

## 1. 现象与错误码

| 用户可见 | 上游 code | 官方含义 | 是否已用日志证实 |
|----------|-----------|----------|------------------|
| 连接语音识别服务失败 | —（握手 401） | 鉴权失败 | ✅ 旧 `X-Api-Access-Key` + `X-Api-App-Key` |
| 上游错误 code=**45000151** | 45000151 | **音频格式不正确** | ✅ 改协议前，首包 PCM 后约 1s |
| 上游错误 code=**45000081** | 45000081 | **等包超时** | ✅ local 轨从未送 PCM 时 ~13s；挂断清理时偶发 |

实验 A 改协议后：**remote 轨** 已出现 `asr.partial` / `asr.final`（如 `456789 hello，everyone。`），**45000151 消失**。

---

## 2. 根因（按优先级，均有证据）

### 2.1 鉴权：仅支持「新版本控制台」（必须）

当前仓库 `back/src/services/volc_asr/client.py` 使用 **旧版** 头：

```http
X-Api-Access-Key: ...
X-Api-App-Key: ...
```

新版本控制台（文档「新版本控制台」节）要求：

```http
X-Api-Key: <控制台 API Key>
X-Api-Resource-Id: volc.seedasr.sauc.duration   # ASR 2.0 小时版示例
X-Api-Request-Id: <uuid>
X-Api-Sequence: -1
```

- **不要**再实现旧版双 Key 切换；只支持新鉴权。
- `VOLC_ASR_ACCESS_KEY`  env 名可保留，语义改为存 **X-Api-Key** 的值。
- 401 → `upstream_connect_failed` 在 `asr_proxy.py` 的 `connect()` / `send_full_request()` 异常分支。

### 2.2 协议：audio-only 帧 header 错误 → 45000151（必须）

文档 Message flow 规定：

| 包类型 | serialization | compression |
|--------|---------------|-------------|
| full client request | **JSON** (`0x1`) | gzip |
| **audio-only** | **none / raw** (`0x0`) | gzip |

当前 `back/src/services/volc_asr/protocol.py` 的 `build_audio_only_request` 沿用 default **JSON**，导致上游 **45000151**。

**修复（实验 A 已验证）**：

1. `build_full_client_payload` 中 `audio.format`: **`"pcm"`**（`codec: "raw"`，16k/mono/16bit 不变）。
2. `build_audio_only_request` 调用 `_header_bytes(..., serialization=SERIALIZATION_NONE)`，其中 `SERIALIZATION_NONE = 0b0000`。
3. 验证：首帧 audio header 应为 `ser=0`（Back 日志示例：`header_hex=11210100 msg_type=2 flags=1 ser=0 comp=1`）。

### 2.3 Resource ID 与产品代际（必须配 env）

| 产品 | Resource ID |
|------|-------------|
| 豆包流式 ASR **1.0** | `volc.bigasr.sauc.duration` |
| 豆包流式 ASR **2.0**（Seed） | `volc.seedasr.sauc.duration` |

当前 `.env.example` 仍为 1.0；2.0 账号必须改为 `volc.seedasr.sauc.duration`，否则即使鉴权通过也可能异常。

WS URL 通话实时字幕用：**`wss://openspeech.bytedance.com/api/v3/sauc/bigmodel`**（双向流式），不要用 demo 默认的 `bigmodel_nostream`。

### 2.4 Front：local 轨过早 `asr.start` 且无重试 → 45000081（应修）

**已证实（非主因于 45000151，但影响「我说」栏）**：

- `front/src/stores/asr.ts` 在 `in_call` 时 **同时** 发送 local + remote 的 `asr.start`。
- 日志：`local_stream_missing`（`getLocalStream()` 仍为 null）→ 该端 **从未** `first_pcm_send track=local`。
- Back：`track=local ... upstream_error 45000081 had_browser_pcm=False`。

**建议实现**：

- **仅在有 MediaStream 时再 `asr.start` + 开采集**（local / remote 分别 watch）。
- 或：`getUserMedia` / WebRTC `ontrack` 就绪后再 start 对应 track。
- **不要**对从未送过 PCM 的 track 在上游空等至超时；挂断时 `asr.stop` 前若未 start 则 skip。

remote 轨：可在 `remoteStream` 就绪后再 `asr.start`，减少空等（本次 remote 在 ~500ms 内有流，非 45000151 主因）。

### 2.5 怀疑已排除

- **怀疑 1（remote 过早 start 导致 45000151）**：❌ 实验 A 下 remote 有 PCM 后仍曾 45000151；改 header 后消失。
- **demo 脚本**：鉴权、resource、URL、分包方式均不可直接照搬。

---

## 3. 必改文件清单

| 文件 | 改动要点 |
|------|----------|
| `back/src/services/volc_asr/client.py` | `_auth_headers()` → 仅 `X-Api-Key` + `X-Api-Sequence: -1`（值来自 settings） |
| `back/src/services/volc_asr/protocol.py` | `format: pcm`；audio-only `SERIALIZATION_NONE`；可选 `describe_frame_header()` 仅测试用 |
| `back/.env.example` | `VOLC_ASR_RESOURCE_ID=volc.seedasr.sauc.duration`；注释说明 `VOLC_ASR_ACCESS_KEY` = 新控制台 API Key |
| `back/src/services/asr_proxy.py` | 检查 `send_full_request` 返回的 `code`；upstream 异常写 log（含 `X-Tt-Logid` 若可取）；**不要**吞异常无日志 |
| `front/src/stores/asr.ts` | local/remote 分轨延迟 start；去掉联调用的 `[ASR-TIMELINE]` |
| `back/tests/test_volc_asr_protocol.py` | 断言 `format==pcm`、audio-only `ser==0` |
| `README.md` | 新鉴权、2.0 resource、勿用 demo 作唯一参考 |

**不要提交**：`experiment=A` 时间线日志、`uvicorn.error` 双写、Front 大量 `console.info` 调试。

---

## 4. 环境变量（Back `.env`）

```env
# 新控制台 API Key → 映射为 X-Api-Key
VOLC_ASR_ACCESS_KEY=<控制台 API Key>

VOLC_ASR_WS_URL=wss://openspeech.bytedance.com/api/v3/sauc/bigmodel
VOLC_ASR_RESOURCE_ID=volc.seedasr.sauc.duration   # ASR 2.0；1.0 用 volc.bigasr.sauc.duration
VOLC_ASR_SEGMENT_MS=200
```

Front：**禁止** `VITE_VOLC_ASR_*`。

---

## 5. 验收标准

### 5.1 单元 / 集成

```bash
cd back && uv run pytest tests/test_volc_asr_protocol.py tests/test_asr_ws.py -v
cd front && npm run build
```

### 5.2 手工（双浏览器）

1. alice 呼叫 bob，接通后 **双方各说几句**。
2. CallsView「我说 / 对方说」均有 partial → final。
3. Console **无** `45000151`；挂断时 **无** 误导性 error toast（45000081 可忽略或降级）。
4. Network：仅 `WS /api/asr/ws` + `/api/calls/ws`，无 Agent。

### 5.3 可选：独立上游探针

用与 `.env` 相同 header 对 `bigmodel` 发 16k mono wav（**不要**依赖未修正的 demo 鉴权/header）。

---

## 6. 联调时间线参考（实验 A 成功的一次）

Front（主叫端 admin，local 未就绪）：

| ms | 事件 |
|----|------|
| 87 | `asr_start` local + remote |
| 87 | `local_stream_missing` |
| 491 | `remote_stream_ready` |
| 754 | `first_pcm_send` **remote only** |
| 3057+ | `asr_partial` / `asr_final` |
| 13591 | 挂断 `remote_stream_pending` → 偶发 `45000081` |

Back（同通话 admin remote）：

- `full_request_response upstream_code=0`
- `first_upstream_audio_segment ... ser=0`
- **无** `45000151`

---

## 7. 后续可选（非阻塞 MVP）

- 挂断时对未激活 track 静默 `cleanup`，不向 UI 抛 `45000081`。
- 记录火山响应头 `X-Tt-Logid` 便于工单。
- 更新 `docs/prd/volcengine-streaming-asr.md` 落地状态与信令表（`asr.track` + binary PCM）。
- **不要**改 `back/demo/sauc_python` 行为；若更新 demo，须与新鉴权 + pcm + ser=0 一致。

---

## 8. 变更日志

| 日期 | 说明 |
|------|------|
| 2026-05-27 | 联调结论：45000151=协议/header；新鉴权 X-Api-Key；local 延迟 start；实验 A 验证 remote 转写成功 |
