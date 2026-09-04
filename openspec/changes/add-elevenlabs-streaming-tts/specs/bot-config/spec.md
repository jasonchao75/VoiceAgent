# Delta: Bot Configuration

## MODIFIED Requirements

### Requirement: Bot configuration persistence

Bot 必须保存 ASR、TTS provider/voice/model、LLM、Prompt 和 Opening Script 配置，并允许 TTS provider 在 Deepgram Flux 与 ElevenLabs 之间切换。

#### Scenario: Save an ElevenLabs bot

- **WHEN** 用户选择 ElevenLabs、选择或填写 voice ID、选择 model 并提交合法配置
- **THEN** Bot 保存 provider/voice/model，后续会话按该配置创建 ElevenLabs streaming TTS

### Requirement: Optional encrypted credential storage

系统必须按当前 Bot 所选 provider 校验所需凭证；Deepgram ASR Key 与 LLM Key 始终需要，ElevenLabs Key 仅在 TTS provider 为 ElevenLabs 时需要。用户选择保存时，每把 Key 必须分别 Fernet 加密。

#### Scenario: ElevenLabs bot saves credentials

- **WHEN** ElevenLabs Bot 选择保存 Key
- **THEN** Deepgram、LLM 和 ElevenLabs 三把 Key 分别加密落库，API 与日志只返回当前配置的凭证是否齐备

#### Scenario: Deepgram TTS bot saves credentials

- **WHEN** Deepgram Flux Bot 选择保存 Key
- **THEN** 只要求并保存 Deepgram 与 LLM Key，不要求 ElevenLabs Key

## ADDED Requirements

### Requirement: ElevenLabs account voice discovery

系统必须允许用户使用临时 ElevenLabs Key 查询当前账号可用 voices，并提供手工 voice ID 降级入口；Key 不得缓存、持久化或写入日志。

#### Scenario: Voice list succeeds

- **WHEN** 用户请求加载 ElevenLabs voices 且 Key 有效
- **THEN** 页面通过统一 Voice Picker 展示安全裁剪后的 voice ID、名称与类别，并支持关键词、语言、口音、性别、来源/类别筛选和分页加载

#### Scenario: Voice filter options follow account metadata

- **WHEN** ElevenLabs voice 查询成功或当前查询结果刷新
- **THEN** 页面从返回的 voice metadata 动态聚合 Language、Accent、Gender 和 Source/Category 可选值，不依赖 Platform 写死枚举；缺失字段统一归入 `Unspecified`

#### Scenario: Filter Deepgram voices

- **WHEN** 用户选择 Deepgram Flux 并搜索或筛选音色
- **THEN** 同一个 Voice Picker 在本地 catalog 中按名称、口音、性别、traits 与 use case 即时过滤

#### Scenario: Voice result set is large

- **WHEN** ElevenLabs 匹配结果超过单页上限
- **THEN** 后端依据 `has_more` 和 `next_page_token` 分页，前端增量加载且保持当前选择不丢失

#### Scenario: Voice list fails

- **WHEN** voice 查询超时、鉴权失败或服务不可用
- **THEN** 页面显示安全错误并保留手工填写 voice ID 的能力
