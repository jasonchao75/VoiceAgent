# Design: Add Call History and Metrics

## 1. Data Model

使用独立的异步 SQLite `history.db` 保存结构化数据，录音文件保存在 `$VOICE_AGENT_DATA_DIR/recordings/`。主要实体：

- `calls`：session、Bot 快照摘要、开始/结束时间、状态、语言、ASR/LLM/TTS 配置标识和错误诊断。
- `turns`：角色、最终文本、turn 序号和服务端时间戳；不持久化 ASR partial。
- `turn_metrics`：ASR final、LLM 首 Token、TTS 首音频、浏览器首次播放等时间点及派生耗时，以及 reasoning token 数量、关闭策略和验证状态。
- `recordings`：相对路径、格式、采样率、声道、字节数、保留截止时间和删除状态。

不复制 Bot API Key、Session token、Authorization header 或完整 System Prompt。Bot 被修改或删除后，历史记录保留必要的非秘密配置快照。

## 2. Recording Strategy

- 只录制用户上行、进入 ASR 前的单声道音频，保持原始 16kHz/16-bit PCM 语义并以无损 FLAC 落盘。
- 音频写入通过有界队列交给后台 writer，核心 Pipeline 不执行同步磁盘 I/O。
- 队列溢出、编码或磁盘写入失败时停止该通话录音并记录原因，不影响实时 ASR、LLM、TTS。
- 录音文件使用随机 ID，不使用 Bot 名称、Transcript 或其他敏感内容作为文件名。

## 3. Retention and Capacity

默认环境变量：

| 配置 | 默认值 | 作用 |
|---|---:|---|
| `VOICE_AGENT_HISTORY_RETENTION_DAYS` | 30 | 文本、指标和元数据保留期 |
| `VOICE_AGENT_RECORDING_RETENTION_DAYS` | 7 | 录音保留期 |
| `VOICE_AGENT_RECORDING_MAX_BYTES` | 5368709120 | 录音配置上限 5GB |
| `VOICE_AGENT_STORAGE_MIN_FREE_BYTES` | 1073741824 | 至少保留 1GB 空间 |

录音有效配额为配置上限与数据卷总容量 20% 的较小值。启动时、通话结束后及周期任务中执行清理：先删过期录音，再按最旧优先删除超额录音。文本到期后删除 call 及关联 turns/metrics；手动删除立即删除结构化记录与录音。

## 4. Metrics Semantics

每轮至少计算：

- `asr_final_latency_ms`：Flux 最后一个识别词结束到服务端收到 `EndOfTurn` final transcript。使用 `words[].end` 与已接收音频累计时钟计算；word timing 缺失或时钟不一致时保存 null，并通过 `asr_final_reason` 说明，不得把负值截断为 0。
- `llm_request_splicing_ms`：ASR final 到用户 aggregator 把上下文推给 LLM 服务（`LLMContextFrame`），即 LLM request splicing。
- `llm_first_token_ms`：`LLMContextFrame` 到服务端观察到首个 `LLMTextFrame`（LLM TTFT）；包含服务器到厂商的公网耗时，不包含浏览器下行播放。
- `tts_initial_ms`：首个 LLM text token 到 TTS 服务开始处理（TTS initial），含后续 token 流式等待与 TTS 服务启动。
- `tts_first_audio_ms`：TTS 服务开始处理到服务端收到首个音频包（TTS TTFT）；包含服务器到厂商的公网耗时。
- `playback_ms`：服务端首个 TTS 音频包到浏览器首次播放回调，主要反映传输、缓冲和客户端播放。
- `turn_to_playback_ms`：用户停止说话到浏览器首次播放（e2e latency）。

以上 6 个 breakdown 项构成完整的延迟链，其和恒等于 `turn_to_playback_ms`。缺失事件必须保存为 null 并标注原因，不得用 0 代替。

缺失事件必须保存为 null 并标注原因，不得用 0 代替。时间点使用单调时钟计算耗时、UTC 时间用于展示和持久化。

每轮额外保存 `incomplete_reason`。用户在 LLM 首 Token、TTS 首音频或浏览器首次播放前打断，以及会话在播放前结束时，前端必须显示具体原因。LLM/TTS/播放事件只有在当前轮的前置事件已经发生时才可归入该轮，防止上一轮残留 frame 污染下一轮。

Reasoning 指标只保存 token 数量与状态，不保存隐藏思维链或 provider 专用 reasoning 内容正文。`reasoning_tokens=null` 表示 provider 未提供证据，与 `0` 严格区分。

## 5. History API and UI

- 列表 API：分页、按时间倒序，返回状态、Bot、时长、是否有录音和摘要指标。
- 详情 API：返回逐轮文本、指标和安全错误诊断。
- 录音 API：Basic Auth 后流式读取或下载，不暴露真实文件路径。
- 删除 API：删除单条通话及录音，要求明确的前端确认。
- 前端新增 History 区域，支持列表、详情、HTML audio 播放/下载及删除。

页面在开始通话前明确提示“用户语音和对话文本将按保留策略保存”。第一阶段不增加逐通话关闭录音的开关。

## 6. ASR Benchmark Compatibility

历史记录保存 `audio_format`、`sample_rate`、`channels`、`language`、`asr_provider`、`asr_model`、最终 Transcript、Bot ID 和 call/turn ID。未来建立 Benchmark 时必须通过独立、人工确认的导出 Change 选择数据，不允许清理任务之外的自动复制或长期保留。

## 7. Deployment and Recovery

- 复用现有 `/data` named volume；数据库与录音不进入镜像和 Git。
- 部署前执行只读磁盘检查，确认有效配额不会挤压系统和 Docker 更新空间。
- schema 通过幂等初始化建立；本 Change 无历史通话数据迁移。
- 回滚代码不删除 `history.db` 或录音；旧版本忽略新增文件。
