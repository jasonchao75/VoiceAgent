# Design: ElevenLabs Bidirectional Streaming TTS

## 1. Official API Contract

- Endpoint: `wss://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream-input`。
- 客户端先发送初始化消息，再持续发送带尾随空格的文本 chunk，以空文本结束；服务端持续返回 Base64 audio chunk 与 `is_final`。
- 使用 `eleven_flash_v2_5`：官方定位为实时场景的低延迟多语种模型；约 75 ms 是模型推理时间，不包含公网与播放缓冲。
- `auto_mode=true`：让服务端自动触发生成，避免手工 chunk schedule 因文本不足而等待。
- `output_format=pcm_24000`，与现有浏览器输出契约一致，避免 Pipeline 增加重采样。
- `apply_text_normalization=auto`；Flash 的数字规范化能力有限，号码、日期、货币仍优先由 LLM 输出可朗读文本。

## 2. Integration Boundary

复用 `TTSProviderRegistry`，注册 `elevenlabs` builder。Pipeline 顺序不变：

`LLM stream → selected TTS service → WebSocket transport output`

使用 Pipecat 1.8.1 自带的 `ElevenLabsTTSService`，该服务继承 `WebsocketTTSService`，负责连接复用、文本输入、音频输出和 cancellation。不得在项目中复制一套 WebSocket 协议实现。

## 3. Configuration

`TTSConfig` 扩展为 provider-aware 配置：

- Common: `provider`, `voice`, `model`, `speed`
- Deepgram-only: `expressivity`
- ElevenLabs: `stability=0.5`, `similarity_boost=0.8`, `style=0`, `use_speaker_boost=true`, `auto_mode=true`, `apply_text_normalization=auto`

第一版允许模型 `eleven_flash_v2_5` 与 `eleven_multilingual_v2`；UI 默认 Flash。Multilingual v2 音质更稳，但延迟与成本更高。

## 4. Voice Discovery

ElevenLabs voices 属于账号资源，不能使用静态全局白名单。后端新增受 Basic Auth 保护的 voice 查询接口：浏览器提交临时 ElevenLabs Key，服务端以显式超时调用官方 voice list API，只返回 `voice_id`、name、category、language/accent 等非秘密字段，不缓存 Key、不写日志。

当 voice 查询失败时，UI 显示安全错误并允许手工填写 voice ID；保存 Bot 时仅校验 voice ID 格式与长度，真实可用性由 voice 查询或会话连接验证。

具体交互与数据流：

1. 用户在 Bot 编辑器选择 `ElevenLabs`，页面显示 ElevenLabs Key、Model 和 Voice 区域。
2. 用户输入临时 Key，或选择已经安全保存 ElevenLabs Key 的 Bot，点击 `Load voices`。
3. 浏览器仅把 Key 发给 Platform 后端；后端调用 `GET https://api.elevenlabs.io/v2/voices`，使用 `xi-api-key` 鉴权、`page_size=100`，并依据 `has_more` / `next_page_token` 完成分页。
4. 后端裁剪响应，只返回 `voice_id`、name、category、labels、preview URL；前端展示可搜索下拉框，并提供试听入口。
5. 用户选择后，Bot 只保存 Voice ID 与显示名称快照；每次合成仍以 Voice ID 为准。
6. 下拉加载失败或用户已有一个未被列表返回的 Voice ID 时，可展开 `Enter voice ID manually` 输入框。

不从 Platform 静态配置维护 ElevenLabs voice 清单，也不让浏览器直接请求 ElevenLabs，避免 API Key 暴露在第三方网络调用和浏览器调试信息中。

### Unified Voice Picker

Deepgram 与 ElevenLabs 共用同一个可搜索 Voice Picker，避免 provider 切换后出现两套操作方式：

- 固定显示关键词搜索；匹配 name、description、accent、traits/use case。
- 一级筛选保留 `Language`、`Accent`、`Gender`；ElevenLabs 额外显示 `Source/Category`（default、personal/cloned、workspace、saved）。
- ElevenLabs 筛选项不使用 Platform 固定枚举：后端从当前账号返回的 voice metadata/labels 聚合并随查询刷新；缺失维度显示为 `Unspecified`。Deepgram 筛选项同样从本地 catalog 动态聚合。
- 默认排序为推荐/最近使用，其次允许按名称排序；已选 Voice 固定显示在顶部，不因翻页消失。
- 每条结果显示名称、语言/口音、类别或特征，并提供 Preview；选择动作与试听动作分离，避免误选。
- 无结果时保留清除筛选与手工 Voice ID 入口。

Deepgram 当前静态 catalog 较小，由浏览器对已加载数据即时筛选；ElevenLabs 使用 `/v2/voices` 的 `search`、language、accent、gender、voice_type/category 参数做服务端筛选，并以 `next_page_token` 增量加载。前端组件和返回 DTO 保持 provider-neutral，只有后端数据适配器不同。

### Approved UI Baseline

页面实现以 `prototypes/index.html` 为交互与视觉基线，入口嵌入现有 Bot 编辑器，不新增独立导航页面。`prototypes/README.md` 维护原型与 Delta Scenario 的映射，`verification/ui-checklist.md` 用于实现后验收。行为冲突时以 Delta Spec 为准；视觉和交互细节以用户确认后的原型为准。

## 5. Credential Model and Migration

ASR 始终需要 Deepgram Key，LLM 需要 LLM Key；只有 `tts.provider=elevenlabs` 时额外需要 ElevenLabs Key。

- `bots` 新增 `encrypted_elevenlabs_key` nullable 列，幂等迁移。
- `SessionCredentials` 新增 nullable `elevenlabs_api_key`，结束时清空引用。
- create/update/session 请求按 provider 校验所需 Key，不再使用固定“两把 Key 全有或全无”的假设。
- `has_saved_keys` 表示当前 Bot 所选 provider 所需的全部凭证已经保存。

## 6. Failure, Timeout, and Observability

- Voice list HTTP 调用 timeout 10 秒。
- TTS WebSocket 连接/写入/关闭沿用 Pipecat service timeout 与 cancellation。
- ElevenLabs 401/403、voice/model 不存在、并发/额度限制统一进入现有 provider error 与 diagnostic 链路。
- 现有 `TTSStartedFrame`、`TTSAudioRawFrame`、browser playback 指标保持 provider-neutral。Pipecat 1.8.1 的 `ElevenLabsTTSService` 已产生公共 `TTSStartedFrame` 与 `TTSAudioRawFrame`；实现仍需用回归测试锁定该契约。
- `CallCapture`、latency 公式、`incomplete_reason` 和 History UI 不增加 provider 分支；两种 TTS 使用完全相同的展示字段和缺失标注。
- 通话历史额外快照 `tts_provider`、`tts_model`、`tts_voice`，以便同口径对比时识别实际厂商配置；旧记录保持可读。

## 7. Verification

- 不调用真实厂商的单元/集成测试覆盖 registry、配置、加密迁移、API schema、前端构建和 pipeline。
- 用户提供 BYOK 后手动执行最小真实验收：Opening Script、正常一轮、连续多轮、barge-in、End session、历史 TTS TTFT。
- 真实验收会消耗 ElevenLabs credits，执行前再次确认。

## Sources

- ElevenLabs WebSocket API: https://elevenlabs.io/docs/api-reference/text-to-speech/v-1-text-to-speech-voice-id-stream-input
- ElevenLabs realtime WebSocket guide: https://elevenlabs.io/docs/eleven-api/guides/how-to/websockets/realtime-tts
- ElevenLabs model comparison: https://elevenlabs.io/docs/overview/models
- ElevenLabs latency guidance: https://elevenlabs.io/docs/api-reference/reducing-latency
