# Design: ElevenLabs Bidirectional Streaming TTS

## 1. Official API Contract

- Endpoint: `wss://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream-input`。
- 客户端先发送初始化消息，再持续发送带尾随空格的文本 chunk，以空文本结束；服务端持续返回 Base64 audio chunk 与 `is_final`。
- 默认使用 `eleven_flash_v2_5`：官方定位为实时场景的低延迟多语种模型；约 75 ms 是模型推理时间，不包含公网与播放缓冲。
- Text aggregation 为平台级配置：`token` 将 LLM text frame 立即发给厂商，`sentence` 在 TTS processor 内聚合到句末后再发送；两者都不等待 LLM 完整回复。
- ElevenLabs Auto mode 不作为独立用户开关：`token` 自动对应 `auto_mode=false`，由厂商 chunk schedule 缓冲与决定生成边界；`sentence` 自动对应 `auto_mode=true`，收到完整句后跳过厂商缓冲。
- `output_format=pcm_24000`，与现有浏览器输出契约一致，避免 Pipeline 增加重采样。
- `apply_text_normalization` 默认 `auto`，也允许高级用户选择 `on/off`；Flash 的数字规范化能力有限，号码、日期、货币仍优先由 LLM 输出可朗读文本。

## 2. Integration Boundary

复用 `TTSProviderRegistry`，注册 `elevenlabs` builder。Pipeline 顺序不变：

`LLM stream → selected TTS service → WebSocket transport output`

使用 Pipecat 1.8.1 自带的 `ElevenLabsTTSService`，该服务继承 `WebsocketTTSService`，负责连接复用、文本输入、音频输出和 cancellation。不得在项目中复制一套 WebSocket 协议实现。

## 3. Configuration

`TTSConfig` 扩展为 provider-aware 配置：

- Common: `provider`, `voice`, `model`, `speed`, `text_aggregation`
- Deepgram-only: `expressivity`
- ElevenLabs: `stability=0.5`, `similarity_boost=0.8`, `style=0`, `use_speaker_boost=false`, derived `auto_mode`, `apply_text_normalization=auto`

第一版允许模型 `eleven_flash_v2_5`、`eleven_turbo_v2_5`、`eleven_multilingual_v2` 与 `eleven_v3`；UI 默认 Flash。定位分别是低延迟、速度/质量平衡、长文稳定和高表现力。

### Voice settings 产品边界

| 配置 | 范围/默认 | 第一版 | 说明 |
|---|---|---|---|
| Text aggregation | token/sentence / token | 开放（公共配置） | Token 优先低延迟；Sentence 优先语调和稳定性；适用于 Deepgram Flux 与 ElevenLabs |
| Stability | 0–1 / 0.5 | 开放 | v2.x 使用连续滑杆；v3 仅提供 Creative (0)、Natural (0.5)、Robust (1) 三档 |
| Similarity boost | 0–1 / 0.8 | 开放 | 影响与原 voice 的相似度；v3 不支持，选中 v3 时禁用且不传递 |
| Style exaggeration | 0–1 / 0 | 开放 | 属于 v2+ voice setting；值越高风格越强，可增加延迟 |
| Speed | 0.7–1.2 / 1 | 开放 | 使用官方 WebSocket 范围 |
| Speaker boost | off / false | 开放 | 可提高相似感，但可能增加生成时间；v3 不支持，选中 v3 时禁用且不传递 |
| Auto mode | derived | 只读说明 | ElevenLabs 专属；Token 时为 off，Sentence 时为 on，不允许用户创建高风险组合 |
| Text normalization | auto/on/off / auto | 高级项 | `auto` 由厂商决定，`on` 强制规范化数字/日期/金额，`off` 原文合成；Flash 的 `on` 可能受账户套餐限制，错误不得静默降级 |

### Provider aggregation capability

| Provider | Token | Sentence | 建议默认 | 厂商内部边界 |
|---|---|---|---|---|
| Deepgram Flux TTS | 支持 | 支持 | Token | Flux 面向原始 LLM 输出设计，在长连接内自行放置合成边界 |
| ElevenLabs WebSocket | 支持 | 支持 | Token | Token 模式保留 ElevenLabs chunk schedule；Sentence 模式启用 Auto mode |

### Defaults and migration

- 新建 Bot 的 `text_aggregation` 默认 `token`。
- 迁移列保持 nullable；未显式保存该字段的旧 Bot 按上线前行为解析：Deepgram Flux 为 Token，ElevenLabs 为 Sentence。用户下次保存后才写入显式选择，避免部署自动改变已有 Bot 的声音和延迟。
- ElevenLabs 运行时由 `text_aggregation` 派生 Auto mode，数据库不存独立 `auto_mode`。

Vapi 还暴露 `optimizeStreamingLatency`、SSML、caching、pronunciation dictionaries 和 fallback voices。本项目的 Pipecat 双向 WebSocket service 不传递 `optimizeStreamingLatency`（该字段属于 HTTP streaming service），因此不创建无效 UI。其余四项涉及文本安全、缓存键/保留策略、资源生命周期或故障编排，应独立设计，不作为本次音色参数的开关。

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

- 固定显示关键词搜索，匹配 name 和 description；一级筛选按原型仅提供 `Language` 和 `Gender`。
- ElevenLabs 的 Language/Gender 不使用 Platform 固定枚举：前端从当前已加载的 voice metadata/labels 聚合并随查询刷新；缺失维度显示为 `Unspecified`。Deepgram 筛选项同样从本地 catalog 动态聚合。Accent 和 Source/Category 作为卡片信息展示，本版不增加筛选控件。
- 默认排序为推荐/最近使用，其次允许按名称排序；已选 Voice 固定显示在顶部，不因翻页消失。
- 每条结果显示名称、语言/口音、类别或特征，并提供 Preview；选择动作与试听动作分离，避免误选。
- 无结果时保留清除筛选与手工 Voice ID 入口。

Deepgram 当前静态 catalog 较小，由浏览器对已加载数据即时筛选；ElevenLabs 将关键词 `search` 传给 `/v2/voices`，并以 `next_page_token` 增量加载，Language 和 Gender 则在浏览器对当前已加载结果即时筛选。前端组件和返回 DTO 保持 provider-neutral，只有后端数据适配器不同。

### Approved UI Baseline

页面实现以 `prototypes/index.html` 为必须通过的交互与视觉基线，入口嵌入现有 Bot 编辑器，不新增独立导航页面。实现必须对齐原型的字段顺序、分组、控件类型、默认值、禁用/联动状态、Voice Picker 弹层而非普通 select、结果卡片、试听、筛选、分页/手工 ID 降级与窄屏布局。`prototypes/README.md` 维护原型与 Delta Scenario 的映射，`verification/ui-checklist.md` 用于实现后验收。行为冲突时以 Delta Spec 为准；视觉和交互细节以用户确认后的原型为准，不得在实现中擅自简化。

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
- `CallCapture`、latency 公式、`incomplete_reason` 和 History UI 不增加 provider 分支；两种 TTS 使用相同的展示字段和缺失标注。
- `tts_initial_ms` 仍定义为首个 LLM text frame 到 `TTSStartedFrame`；Token 模式主要表示 Pipeline handoff，Sentence 模式还包含等待首个句子边界的时间。历史 UI 必须说明这一点，不得把它简化成纯 TTS 厂商延迟。
- 通话历史额外快照 `tts_provider`、`tts_model`、`tts_voice`、`tts_text_aggregation`，以便只在相同聚合模式下做延迟对比；旧记录保持可读。

## 7. Verification

- 不调用真实厂商的单元/集成测试覆盖 registry、配置、加密迁移、API schema、前端构建和 pipeline。
- 用户提供 BYOK 后手动执行最小真实验收：Opening Script、正常一轮、连续多轮、barge-in、End session、历史 TTS TTFT。
- 真实验收会消耗 ElevenLabs credits，执行前再次确认。

## Sources

- ElevenLabs WebSocket API: https://elevenlabs.io/docs/api-reference/text-to-speech/v-1-text-to-speech-voice-id-stream-input
- ElevenLabs realtime WebSocket guide: https://elevenlabs.io/docs/eleven-api/guides/how-to/websockets/realtime-tts
- ElevenLabs model comparison: https://elevenlabs.io/docs/overview/models
- ElevenLabs latency guidance: https://elevenlabs.io/docs/api-reference/reducing-latency
