# Design: Streaming ASR Provider Architecture

## Goals

- 保留 Deepgram Flux 现有行为，增加 Deepgram Nova-3，同时允许一个 Bot 独立选择四家实时 ASR Provider。
- 让 Pipeline 只依赖显式 `ASRService` 公共契约，供应商差异停留在 Adapter。
- 将流式识别与 Turn Detection 解耦，本期明确区分 Provider-native 与 Off；Self-developed 策略留待未来 Change。
- 让 Provider 专属参数可扩展、可校验、可回显，不形成大量可空列。
- 使 AssemblyAI Context 与普通 Prompt/Keyterms 在数据和 UI 上可区分。

## Current State

- `ASRConfig.provider` 和模型使用 Deepgram Literal。
- `run_voice_agent_session` 直接调用 `create_flux_stt`。
- `deepgram_api_key` 同时承担 Deepgram ASR/TTS 凭证。
- Bot 表保存一组 Flux 专属列；Catalog 只返回 Deepgram。
- Pipecat 1.8.1 当前环境可加载 Soniox、AssemblyAI Service；Speechmatics extra 尚未安装。

## Proposed Boundaries

### ASR Service and Provider Registry

`ASRService` 是 Pipeline 唯一可见的识别边界，负责流生命周期、音频输入、统一事件、Turn 收口和可选 Context 更新。`ASRProviderRegistry.create(provider, api_key, config, audio)` 为它选择具体 Adapter。每个注册项负责：

- 将公共音频契约映射到 Provider encoding/sample rate。
- 校验并映射 Provider 专属配置。
- 归一化 Turn Detection、Interim/Final、错误与 metrics。
- 声明是否支持动态 Context 和哪些设置需要重连。

浏览器客户端不直接了解供应商：它只向 VoiceAgent WebSocket 发送 PCM。服务端 `ASRService` 持有 Registry 创建的 Adapter，并把供应商结果转换成统一事件。

### Turn Detection Strategy

Turn Detection Source 与 `ASRService` 协作，但不属于任一供应商 Adapter：

- `provider_native`: Adapter 接收供应商 EOT/endpoint 事件作为最终裁决。
- `off`: 关闭语义、声学或模型原生的智能 Turn Detection，但保留 Provider 支持的 VAD/固定静音边界；不是关闭自动轮次。若 Provider 无 VAD-only 能力，则该选项必须禁用。
- 同一会话只有一个来源能提交 Final Turn；供应商分块 Final 不得被误当成对话轮次结束。
- Catalog 暴露 Provider/model 的能力、关闭方式与端到端可运行性，UI 不允许选择尚未验证或没有可用边界的组合。

### Discriminated Configuration

应用层使用 `provider` 作为 discriminator：

- `DeepgramFluxASRConfig`
- `DeepgramNova3ASRConfig`
- `SpeechmaticsASRConfig`
- `SonioxASRConfig`
- `AssemblyAIASRConfig`

Catalog 的语言控件以 `values` 保存真实 Provider code，并以 `labels` 提供英文语言名。前端组合为 `code (label)`；Soniox 原有搜索同时索引 code 与名称，保存与 Provider wire 始终只提交 code。Soniox 账号目录优先使用 Provider 返回名称，缺失时回退到服务器内置名称表；AssemblyAI 使用服务器版本化名称表。

公共字段仅包含 Provider、Model、Audio Contract 与 Turn source；语言也按 Provider 真实协议进入各自严格模型（单值、hints 数组或 steering 数组不得互换）。持久化采用带 `schema_version` 的 Provider options JSON，并保留可验证迁移。

### Credential Ownership

凭证按 `bot_id + component + provider` 归属并加密保存。运行时按 Bot 当前组件与 Provider 解析凭证；AssemblyAI ASR + Deepgram TTS 分别解析各自 Key，不跨组件复用。不同 Bot 可以保存不同账号的 Key；全局资源复用留给未来资源管理页。

凭证 UI 仍位于对应组件抽屉的 Advanced 之后，沿用现网页的单一密码输入、Show 动作和 `Save API key` 开关。当前 Bot 已保存 Key 时输入框保持空白并显示“留空即沿用”；不得增加独立 `Use saved key` 动作。输入新 Key 并保存只替换当前 Bot 对应组件/Provider 的密文。Bot 配置可在缺少凭证时保存，但真实会话启动必须失败并指明缺失的组件/Provider。

## Provider Mapping

| Provider/model | Pipecat service | Provider-native boundary | Off behavior | Context |
|---|---|---|---|---|
| Deepgram Flux | `DeepgramFluxSTTService` / V2 | Flux model-native EOT | 不提供严格 Off；timeout backstop 仍存在 | Dynamic keyterms/settings |
| Deepgram Nova-3 | V1 live streaming adapter | 不提供本产品定义下的 Provider-native 智能 Turn Detection | 固定 Off；使用正数 `endpointing` 静音阈值，以 `speech_final=true` 收口 | Repeated plain `keyterm`; V1 request options |
| Speechmatics | `SpeechmaticsSTTService` | Smart Turn/Adaptive | Fixed silence；`end_of_utterance_mode=FIXED` + 正数 `conversation_config.end_of_utterance_silence_trigger` | Additional vocabulary；非 conversation history |
| Soniox | `SonioxSTTService` | Semantic endpoint → `<end>`；固定 Provider native | Off 禁用，不提交 `enable_endpoint_detection=false` | Session-level general/text/terms；语言目录来自 `GET /v1/models` 对应模型的 `languages[]` |
| AssemblyAI | `AssemblyAISTTService` | U3.5 Pro punctuation/context End-of-Turn + max-silence fallback；固定 Provider native | Provider API 无 VAD-only 模式，Off 禁用；local VAD + `ForceEndpoint` 属未来 Self-developed/external 范围 | Agent Context + automatic Final user carryover |

Speechmatics 与 Soniox 的账号目录刷新入口位于 Advanced 顶部，使用紧凑次级描边样式。入口只对已保存、Provider 匹配且具有匹配 ASR Key 的 Bot 启用；请求期间禁用并显示 loading，避免重复调用。

### Speechmatics Segment and Punctuation Mapping

- 页面“Emit completed sentences”不是 Realtime WebSocket 的同名请求字段；Adapter 将其映射到 Voice SDK `speech_segment_config.emit_sentences`。`AddSegment` 可在一次 Turn 内多次出现，只有 `EndOfTurn` 能驱动用户 Turn 聚合器向 LLM 提交。
- `end_of_utterance_max_delay` 使用 Voice SDK 默认 `10.0 s`，唯一公开数值约束是严格大于 `end_of_utterance_silence_trigger`；UI 和后端使用动态关系校验，不设虚构上限。
- `punctuation_overrides.permitted_marks` 在产品配置中是 `"all"`（默认）或标点字符串数组。UI 先选择 All/Custom；Custom 按一行一个 Unicode 标点字符录入并结合 Language Pack 支持集校验。Adapter 必须将 `"all"` 映射为 wire 字段省略；Speechmatics 服务端只接受数组形态的显式子集。
- 当前项目通过 `pyproject.toml` 锁定官方 `pipecat-ai==1.8.1`。该版本 `pipecat/services/speechmatics/stt.py::_build_config` 的通用字段循环会先尝试把 `split_sentences` 直接写入 `VoiceAgentConfig`，随后才写入正确的 `speech_segment_config.emit_sentences`；这是 Pipecat 官方 Speechmatics Adapter 的待确认兼容风险，不是 Speechmatics 服务端已确认缺陷。实现阶段必须先在不使用 API Key 的配置构造测试中确认顶层赋值是否会被 SDK 拒绝；若失败，VoiceAgent 薄 Adapter 必须绕过该顶层赋值并显式构造 `SpeechSegmentConfig(emit_sentences=...)`。Mock frame 测试必须证明 `AddSegment` 只累计文本、不会提前触发 LLM，只有 `EndOfTurn` 才提交一次完整用户 Turn；上述检查通过后，才进入逐次授权的 external-real 流式验证。

### Deepgram Model Separation

- Flux 使用 V2 `/v2/listen`、`flux-general-en` / `flux-general-multi`、`language_hint[]` 和 `eot_threshold` / `eot_timeout_ms`。
- Nova-3 使用 V1 `/v1/listen`、`model=nova-3`、单个 `language` BCP-47 code；本期固定 Off，但提交正数 `endpointing` 静音阈值并消费 `speech_final=true` 作为 VAD/固定静音轮次边界；其余配置包含 `interim_results`、`vad_events`、`smart_format`、`numerals`、`profanity_filter`、`redact`、`diarize_model` 和重复 `keyterm`。
- Nova-3 不接受 Flux EOT 参数或 `language_hint[]`；`keyterm` 不接受权重，每个短语作为独立 query 参数提交。
- `smart_format=true` 时不再单独暴露冗余的 `punctuate` 开关；语言与参数支持状态从 Catalog 校验。

## AssemblyAI Context Flow

1. 建连时把 Opening Script 作为 `agent_context`。
2. 同一 WebSocket 接收并 Final 用户 Turn；Provider 自动维护用户侧 carryover。
3. LLM 文本块持续进入 TTS；Assistant aggregator 在独立分支形成当前 Agent Turn 的回复。
4. 每个 Agent Turn 只发送一次 `agent_context`；它不等待 TTS 音频返回或播放完成，Context 失败也不阻塞 TTS。
5. Context 只使用本轮 Agent 回复；barge-in 不依据 Web/SIP 播放游标截取，也不在同一 Turn 内渐进更新。
6. 只记录 context mode、长度 bucket、hash 和应用结果；不在 metrics/log 中复制正文。

## AssemblyAI Mode and VAD Mapping

- `mode` 提供三组官方起点：`min_latency=128/640/0 ms`、`balanced=128/1280/500 ms`、`max_accuracy=512/2560/500 ms`，依次对应 `min_turn_silence` / `max_turn_silence` / `interruption_delay`。
- UI 切换 Mode 时必须原子覆盖并回填三个值；用户可在此基础上修改，修改后以“当前 Mode 已修改”表达，不引入 Provider 不存在的 `custom` 枚举。
- 持久化与建连/动态更新保存 `mode` 和三个最终显式值；同一次配置消息不得只切 Mode 而遗留旧显式值。
- `vad_threshold` 是 AssemblyAI 内置 Silero VAD 的独立语音活动阈值，默认 `0.3`、范围 `0.0–1.0`；较低值更敏感，较高值减少噪声误触发但增加轻声漏检风险。若 Pipeline 同时启用 local Silero VAD，实现与验证必须检查两个阈值是否产生检测死区。

## UI Design

- 复用现有 Bot Settings、Pipeline cards 和右侧非模态抽屉。
- Provider 使用单一下拉列表，避免供应商增加后平铺卡片失控；Model、真实语言参数、Audio、Turn source 和 Key 保持基础区。
- 基础区提供 Turn Detection source；本期只显示 Provider native 与 Off，并按 Provider/model capability 禁用不可运行组合。
- Provider 专属设置统一放入 Advanced，并严格绑定官方字段；选择 Off 只隐藏智能 Turn 字段，仍展示 VAD/固定静音阈值，不得隐藏 Context、词汇与格式化配置。
- Deepgram Model 切换必须同时替换语言控件和 Advanced：Flux 与 Nova-3 不共享 Turn、语言和格式字段。
- AssemblyAI 使用 `language_codes[]` 多选 steering（最多 10，空值为 18 语种自动 code-switch），不得使用单语言下拉或固定“Arabic + English”选项。
- 窄屏抽屉进入单列并占满内容区，所有 grid 使用 `minmax(0, 1fr)`，长文本换行。

## Failure and Degradation

- Provider 配置或凭证无效：拒绝创建会话。
- 连接中断：结束当前会话；不把 partial 固化为 Final。
- Assembly Context 更新失败：基础 ASR 可继续，但该轮标记 `context_applied=false` 与安全原因。
- 不实施跨 Provider 自动降级；避免在用户不知情时改变数据接收方、成本和识别行为。

## Evidence Plan

- `static`: PRD、Delta Spec、原型、配置模型审阅。
- `fixture`: 正式 UI 使用固定 Provider Catalog 和 Bot fixture。
- `mock`: Adapter 请求映射、Frame/错误/重连行为。
- `local-real`: 本地 WebSocket 会话路径与无付费路径。
- `external-real`: 每家真实 Key、短测试音频和受控费用；必须另行逐次授权。

## Current Technical Evidence

- Deepgram Flux supports fully manual turns with `eot_threshold=1.0` and `ForceEndTurn`: https://developers.deepgram.com/docs/flux/force-end-turn
- Deepgram officially distinguishes Flux model-native Turn Detection from Nova-3 general ASR; Nova-3 V1 exposes silence endpointing and model-specific language/options: https://developers.deepgram.com/docs/flux/flux-nova-3-comparison and https://developers.deepgram.com/reference/speech-to-text/listen-streaming
- AssemblyAI supports live `agent_context` updates on the active stream for the following user turn: https://www.assemblyai.com/docs/streaming/updating-configuration-mid-stream
- Speechmatics current Language Pack metadata comes from Feature Discovery; Enhanced is selected with `model=enhanced`, and Realtime requires an explicit language pack rather than Batch-only `auto`: https://docs.speechmatics.com/speech-to-text/languages
- Speechmatics FIXED mode uses the configured positive silence threshold literally; a `0` threshold disables turn detection entirely: https://github.com/speechmatics/speechmatics-academy/blob/main/basics/07-turn-detection/README.md
- Speechmatics Voice SDK maps sentence emission to `SpeechSegmentConfig.emit_sentences`, defaults `end_of_utterance_max_delay` to `10.0`, and only requires it to exceed the silence trigger: https://github.com/speechmatics/speechmatics-python-sdk/blob/main/sdk/voice/speechmatics/voice/_models.py
- Speechmatics punctuation uses omission for all supported marks and accepts an explicit array only for a subset; the product persists `"all"` as its UI sentinel. Sensitivity defaults to `0.5` in range `0–1`: validated by the 2026-09-28 external-real protocol response and the vendor API guide.
- AssemblyAI Universal-3.5 Pro Realtime uses punctuation/context-based endpointing bounded by `min_turn_silence` and a forced `max_turn_silence`; it does not expose the legacy confidence-threshold switch as a Provider-side VAD-only mode: https://www.assemblyai.com/docs/voice-agents/best-practices
- Local Pipecat 1.8.1 exposes external/native modes for Speechmatics、Soniox and AssemblyAI; its Deepgram Flux service emits external turn proposals, but the outbound `ForceEndTurn` path remains an implementation verification item.
