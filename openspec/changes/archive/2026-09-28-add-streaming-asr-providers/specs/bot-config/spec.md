# Bot Configuration Delta Specification

## MODIFIED Requirements

### Requirement: Shared Bot configuration

系统 MUST 允许已通过 VoiceAgent 产品登录页和安全 Cookie 会话认证的用户，在单实例内创建、读取、更新和删除共享 Bot。Bot 必须保存 ASR、TTS provider/voice/model/text aggregation、LLM、Prompt 和 Opening Script 配置，并允许 TTS provider 在 Deepgram Flux 与 ElevenLabs 之间切换。ASR MUST 允许在 `deepgram`、`speechmatics`、`soniox`、`assemblyai` 四个实时 Provider 中选择一个，并在 Deepgram 下选择 Flux 或 Nova-3；系统 MUST 保存受 Catalog 约束的 model、language、Turn Detection source 与 Provider/model 专属配置。Provider 或 model 切换不得把旧配置分支的专属字段提交给新分支。

#### Scenario: Restart after creating a Bot

- **WHEN** 用户创建 Bot 后重启应用或容器，并继续使用相同数据卷
- **THEN** Bot 配置仍然存在

#### Scenario: Configure TTS text aggregation

- **WHEN** 用户为 Deepgram Flux 或 ElevenLabs 选择 `token` 或 `sentence`
- **THEN** Bot 保存该平台级配置，会话使用对应 TTS processor 聚合策略，页面说明低延迟与语调稳定性的取舍

#### Scenario: Save an ElevenLabs bot

- **WHEN** 用户选择 ElevenLabs、选择或填写 voice ID、选择 model 并提交合法配置
- **THEN** Bot 保存 provider/voice/model/text aggregation 与 voice settings，后续会话按该配置创建 ElevenLabs streaming TTS

#### Scenario: Configure an ElevenLabs voice

- **WHEN** 用户选择 Flash v2.5、Turbo v2.5、Multilingual v2 或 Eleven v3，并调整合法的 Stability、Similarity、Style、Speed、Speaker Boost 和 Text normalization
- **THEN** Bot 保存这些配置，再次编辑时完整回显，会话创建时传入 ElevenLabs WebSocket service

#### Scenario: Reject an invalid ElevenLabs voice setting

- **WHEN** 数值超出对应范围，或选择了非允许的 model
- **THEN** API 返回字段级校验错误，不保存也不静默修改用户输入

#### Scenario: Preserve existing aggregation behavior during migration

- **WHEN** 旧 Bot 没有显式 `text_aggregation`
- **THEN** Deepgram Flux 按 Token 解析，ElevenLabs 按 Sentence 解析；系统不得因为数据库迁移自动改变已有 Bot 行为

#### Scenario: Select Eleven v3

- **WHEN** 用户选择 `eleven_v3`
- **THEN** Stability 改为 Creative/Natural/Robust 三档，Similarity 与 Speaker Boost 禁用且不传入厂商请求，页面明确说明该模型限制

#### Scenario: Select a streaming ASR provider

- **WHEN** 用户在 ASR 抽屉选择任一受支持 Provider
- **THEN** 页面通过单一下拉列表选择 Provider，从后端 Catalog 加载对应 model/真实语言参数，展示该 Provider 的专属 Advanced 字段并隐藏其他 Provider 字段

#### Scenario: Edit a legacy Deepgram Bot

- **WHEN** 旧 Bot 在迁移后首次打开
- **THEN** 它继续选择 Deepgram Flux，现有 ASR 行为、模型和参数不发生隐式变化

### Requirement: Catalog-backed Bot validation

Bot 的 ASR Provider、model、language、可用 Turn Detection source 和允许组合，以及 TTS provider/voice 与 LLM endpoint，MUST 复用服务器 Catalog 与会话配置的校验来源；前端不得发明供应商能力。

#### Scenario: Submit an unsupported configuration

- **WHEN** 用户提交非法 provider、voice 或受控 provider 的错误 base URL
- **THEN** 系统拒绝写入 Bot

#### Scenario: Submit a stale or fabricated ASR combination

- **WHEN** 客户端提交 Catalog 不支持的 Provider/model/language 组合
- **THEN** API 拒绝保存并返回安全字段错误，不静默替换成默认值

#### Scenario: Configure AssemblyAI language steering

- **WHEN** 用户选择 AssemblyAI Universal-3.5 Pro
- **THEN** 页面以可选多选控件编辑 `language_codes[]`，每项显示 `code (English language name)`；允许留空使用 18 语种原生 code-switch，最多选择 10 项，不得呈现为单语言下拉，提交值仍为原始 code

### Requirement: Optional encrypted key storage

用户 MUST 显式选择是否保存 Bot API Key。保存的 Key MUST 按 `bot_id + component + provider` 使用 `VOICE_AGENT_STORAGE_KEY` 加密归属；不同 Bot MAY 保存不同 Key。Bot MAY 在当前组件/Provider 缺少 Key 时保存非密钥配置，但 MUST 阻止真实会话启动。系统必须按 Bot 当前 ASR、TTS 和 LLM Provider 分别校验所需凭证，API 响应只能返回是否已保存密钥的布尔状态，不得返回明文或密文。

#### Scenario: Read a saved-key Bot

- **WHEN** 客户端查询已保存密钥的 Bot
- **THEN** 响应包含组件凭证是否已保存的布尔状态，但不包含密钥明文或密文

#### Scenario: Storage key is unavailable

- **WHEN** 服务未配置有效的 `VOICE_AGENT_STORAGE_KEY`
- **THEN** 应用仍可启动且纯 BYOK 路径可用，但保存或解密 Bot Key 的操作返回明确错误

#### Scenario: ElevenLabs bot saves credentials

- **WHEN** ElevenLabs Bot 选择保存 Key
- **THEN** 当前 ASR Provider、LLM 和 ElevenLabs TTS 三把 Key 按组件与 Provider 分别加密落库，API 与日志只返回当前配置的凭证是否齐备

#### Scenario: Deepgram TTS bot saves credentials

- **WHEN** Deepgram Flux TTS Bot 选择保存 Key
- **THEN** 系统分别保存当前 ASR Provider、Deepgram TTS 与 LLM Key，不要求 ElevenLabs Key

#### Scenario: Configure AssemblyAI ASR with Deepgram TTS

- **WHEN** Bot 同时选择 AssemblyAI ASR 与 Deepgram TTS
- **THEN** 系统分别解析 AssemblyAI ASR Key 与 Deepgram TTS Key，不把任一 Key 复用到另一组件

#### Scenario: Switch ASR provider

- **WHEN** 用户从一个 ASR Provider 切换到另一个 Provider
- **THEN** Bot 只解析当前 Bot 为新 Provider 保存的 ASR Key，不得把旧 Provider Key 当作新 Provider Key

#### Scenario: Keep provider keys isolated across bots

- **WHEN** 多个 Bot 选择相同组件和 Provider
- **THEN** 每个 Bot 独立解析自己的加密 Key，更新一个 Bot 不得影响其他 Bot

#### Scenario: Render provider credentials in the component drawer

- **WHEN** 用户编辑 ASR 配置
- **THEN** Key 区域位于 Advanced 之后，沿用现网页的单一密码输入、Show 动作和 `Save API key` 开关；当前 Bot 已有 Key 时留空自动沿用，不展示 `Use saved key` 按钮

#### Scenario: Replace the current Bot provider key

- **WHEN** 用户输入新 Key 并选择保存
- **THEN** 系统只原子替换当前 Bot 对应组件/Provider 的密文，其他 Bot 不受影响

## ADDED Requirements

### Requirement: Provider-specific ASR configuration

系统 MUST 以严格、互斥的 Provider 配置模型保存 Advanced 参数，并在 UI 中解释参数对准确率、延迟或 Context 的影响；未知字段必须被拒绝。

#### Scenario: Preserve current Deepgram advanced controls

- **WHEN** 用户选择 Deepgram Flux
- **THEN** Advanced 按当前线上顺序展示 EOT threshold、EOT timeout、Keyterms、Profanity filter、Numerals 和 Redact，字段范围与现有契约一致

#### Scenario: Configure Deepgram Nova-3

- **WHEN** 用户在 Deepgram 下选择 `nova-3`
- **THEN** 页面使用 Catalog-backed `language` BCP-47 单选与 Nova-3 V1 Streaming 参数，Turn Detection Source 固定为 `off` 并禁用 Provider native；请求提交正数 `endpointing` 静音阈值并以 `speech_final=true` 收口，展示 `interim_results`、`vad_events`、重复 `keyterm`、`smart_format`、`numerals`、`profanity_filter`、`redact` 和 `diarize_model`，不得展示或提交 Flux EOT 或 `language_hint[]`

#### Scenario: Enter Nova-3 keyterms

- **WHEN** 用户为 Nova-3 输入多条 Keyterm
- **THEN** 每个非空行映射为一个重复的 plain `keyterm` 参数，不附加权重，也不把逗号、分号或整块文本作为多词条编码

#### Scenario: Configure Soniox context

- **WHEN** 用户选择 Soniox 并填写 general/text/terms Context
- **THEN** 系统按 Soniox session-level Context 保存，页面不得宣称它会在同一连接内随每轮 Agent 回复动态更新

#### Scenario: Select Soniox language hints

- **WHEN** 用户点击 `Add language hint`、搜索并选择一个或多个 Soniox 语言
- **THEN** 页面只允许从后端 Catalog 映射的 `stt-rt-v5.languages[]` 中多选 ISO code，每项显示 `code (English language name)` 且可按 code 或语言名搜索；支持逐项移除与全部清空，不接受自由输入；空数组明确表示自动多语识别，提交值仍为原始 code

#### Scenario: Refresh an account-filtered catalog

- **WHEN** 用户查看已保存匹配 Provider Key 的 Speechmatics 或 Soniox Bot
- **THEN** Advanced 顶部展示带刷新图标的紧凑次级描边按钮；刷新期间按钮显示 loading 且禁用；Bot 尚未保存、Provider 不匹配或无匹配 Key 时按钮禁用并解释原因

#### Scenario: Configure Speechmatics enhanced

- **WHEN** 用户选择 Speechmatics
- **THEN** 系统固定提交 `model=enhanced`，并从 Speechmatics Discovery/Catalog 展示账号可用的完整 Language Pack（含单语、双语和多语 code）；Realtime 不得提供 `auto`，也不得把少量示例语言当成完整枚举

#### Scenario: Select a Speechmatics language pack

- **WHEN** 用户选择 `ar_en`、`en_ms`、`cmn_en` 或其他 Catalog Pack
- **THEN** 系统原样保存官方 `language` code，并只展示该 Pack 对应的 domain/locale 选项

#### Scenario: Configure Speechmatics sentence emission

- **WHEN** 用户启用 Emit completed sentences
- **THEN** 系统映射为 Voice SDK `speech_segment_config.emit_sentences=true`，允许同一用户 Turn 内产生多个稳定句子 Segment，但只有真实 `EndOfTurn` 才能提交一次完整用户 Turn 给 LLM

#### Scenario: Configure Speechmatics maximum EOU delay

- **WHEN** 用户配置 `end_of_utterance_max_delay`
- **THEN** 新配置默认显示 `10.0 s`，且必须严格大于当前 `end_of_utterance_silence_trigger`；页面不得虚构 SDK 未声明的固定数值上限

#### Scenario: Configure Speechmatics punctuation overrides

- **WHEN** 用户保留全部标点或选择自定义标点子集
- **THEN** 系统持久化特殊值 `permitted_marks="all"` 或按行解析且经所选 Language Pack 校验的 `list[string]`，并将 `sensitivity` 校验为 `0–1`、默认 `0.5`
- **AND** Adapter 必须将 `"all"` 映射为 Speechmatics wire 字段省略，只在自定义子集时发送 `permitted_marks: list[string]`

#### Scenario: Configure AssemblyAI context modes

- **WHEN** 用户选择 AssemblyAI
- **THEN** 页面分别展示 Prompt、Keyterms、Agent Context 和 automatic user carryover，不把四者合并成一个模糊的 Context 字段

#### Scenario: Configure AssemblyAI Mode with editable preset values

- **WHEN** 用户选择 `min_latency`、`balanced` 或 `max_accuracy`
- **THEN** 页面必须立即用该 Mode 的官方预设覆盖并回填 `min_turn_silence`、`max_turn_silence` 和 `interruption_delay`，允许用户继续修改，并保存 Mode 与三个最终值；不得增加 Provider 不存在的 `custom` Mode

#### Scenario: Configure AssemblyAI VAD sensitivity

- **WHEN** 用户调整 `vad_threshold`
- **THEN** 页面必须将其表达为范围 `0.0–1.0`、默认 `0.3` 的内置 Silero VAD 语音检测灵敏度，明确说明较低值更敏感、较高值减少噪声误触发；不得将它描述为语义完整度或 Mode 预设字段

#### Scenario: Select Turn Detection source

- **WHEN** 用户选择 Catalog 标记为可运行的 `provider_native` 或 `off`
- **THEN** 页面只替换或隐藏 Provider-native Turn 参数并保存单一 Turn 来源，Provider 的语言、Context、词汇和格式化参数继续显示；Self-developed 不得作为本期选项出现

#### Scenario: Disable an unusable Off combination

- **WHEN** 当前 Provider/model 关闭原生 Turn Detection 后没有自动轮次边界，且 VoiceAgent 尚无 Self-developed detector
- **THEN** 页面禁用 Off 并展示具体原因，不得让用户保存一个被描述为可自动进入 LLM/TTS 的配置

#### Scenario: Apply fixed Turn source capability

- **WHEN** 用户选择 Soniox `stt-rt-v5` 或 Deepgram Nova-3
- **THEN** Soniox 只允许 `provider_native` 且禁用 Off，Nova-3 只允许 `off` 且禁用 Provider native；页面按 Catalog 的 allowed/default source 自动切换并解释限制

#### Scenario: Disable Speechmatics Turn Detection

- **WHEN** Speechmatics 的 Turn Detection Source 为 `off`
- **THEN** 页面把模式固定为 Fixed silence 并保留正数静音阈值；系统提交 `end_of_utterance_mode=FIXED` 与正数 `conversation_config.end_of_utterance_silence_trigger`，不得提交会完全关闭 EndOfUtterance 的 `0`

#### Scenario: Disable unsupported AssemblyAI Off

- **WHEN** 用户选择 AssemblyAI Universal-3.5 Pro Realtime
- **THEN** Turn Detection Source 固定为 `provider_native` 且 Off 禁用；页面说明该模型的 Provider API 没有 VAD-only 模式，`max_turn_silence` 只是内置智能 Turn Detection 的固定静音兜底

### Requirement: ASR drawer prototype conformance

ASR 抽屉 MUST 遵循本 Change 经 User Gate 1 冻结的原型，复用现有 Pipeline card 与右侧非模态抽屉；桌面和窄屏不得产生横向滚动。

#### Scenario: Render desktop and narrow ASR configuration

- **WHEN** 页面处于固定桌面或窄屏视口，并显示最长 Provider 名称和 Context 文案
- **THEN** 字段收缩/换行正确，抽屉 `scrollWidth <= clientWidth`，只允许必要纵向滚动
