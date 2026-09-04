# Delta: Bot Configuration

## MODIFIED Requirements

### Requirement: Shared Bot configuration

系统 MUST 允许在受 Basic Auth 保护的单实例内创建、读取、更新和删除共享 Bot。Bot 必须保存 ASR、TTS provider/voice/model/text aggregation、LLM、Prompt 和 Opening Script 配置，并允许 TTS provider 在 Deepgram Flux 与 ElevenLabs 之间切换。

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

### Requirement: Optional encrypted key storage

用户 MUST 显式选择是否保存 Bot API Key。系统必须按当前 Bot 所选 provider 校验所需凭证；Deepgram ASR Key 与 LLM Key 始终需要，ElevenLabs Key 仅在 TTS provider 为 ElevenLabs 时需要。用户选择保存时，每把 Key 必须分别使用 `VOICE_AGENT_STORAGE_KEY` 加密后写入 SQLite；API 响应只能返回是否已保存密钥的布尔状态。

#### Scenario: Read a saved-key Bot

- **WHEN** 客户端查询已保存密钥的 Bot
- **THEN** 响应包含 `has_saved_keys`，但不包含密钥明文或密文

#### Scenario: Storage key is unavailable

- **WHEN** 服务未配置有效的 `VOICE_AGENT_STORAGE_KEY`
- **THEN** 应用仍可启动且纯 BYOK 路径可用，但保存或解密 Bot Key 的操作返回明确错误

#### Scenario: ElevenLabs bot saves credentials

- **WHEN** ElevenLabs Bot 选择保存 Key
- **THEN** Deepgram、LLM 和 ElevenLabs 三把 Key 分别加密落库，API 与日志只返回当前配置的凭证是否齐备

#### Scenario: Deepgram TTS bot saves credentials

- **WHEN** Deepgram Flux Bot 选择保存 Key
- **THEN** 只要求并保存 Deepgram 与 LLM Key，不要求 ElevenLabs Key

### Requirement: Bot key update semantics

更新 Bot 时 MUST 支持保留、替换和清除已保存 Key。Deepgram Key 与 LLM Key 始终必须同时存在或同时为空；ElevenLabs Key 只在当前 TTS provider 为 ElevenLabs 时参与凭证齐备性判断。

#### Scenario: Edit configuration without submitting keys

- **WHEN** 用户修改已保存 Key 的 Bot 配置但不提交新 Key
- **THEN** 系统保留原有加密 Key

#### Scenario: Switch away from ElevenLabs without clearing its key

- **WHEN** 用户将 TTS provider 从 ElevenLabs 切换为 Deepgram Flux 且未显式清除 Key
- **THEN** 系统可保留已加密的 ElevenLabs Key，但 `has_saved_keys` 只按 Deepgram 和 LLM Key 计算

## ADDED Requirements

### Requirement: Approved prototype conformance

Bot 编辑器的 TTS 配置 MUST 严格遵循已确认的 `prototypes/index.html`，不得用普通 select 或另一套布局替代原型中的 Voice Picker 和 Voice tuning 交互。

#### Scenario: Implement the approved Bot editor

- **WHEN** 开发完成 TTS 配置页面
- **THEN** 字段顺序、分组、控件形态、默认值、provider/model 联动、禁用状态、Voice Picker 弹层、卡片、试听、筛选、分页、手工 ID 和响应式布局与原型一致

#### Scenario: Prevent a simplified voice selector regression

- **WHEN** 实现或后续改动 Voice 选择器
- **THEN** 自动化 UI 检查与人工截图对照必须确认搜索、动态筛选、试听、选中卡片、分页与手工 Voice ID 入口均可用，不得退化为原生下拉框

### Requirement: ElevenLabs account voice discovery

系统 MUST 允许用户使用临时 ElevenLabs Key 查询当前账号可用 voices，并提供手工 voice ID 降级入口；Key 不得缓存、持久化或写入日志。

#### Scenario: Voice list succeeds

- **WHEN** 用户请求加载 ElevenLabs voices 且 Key 有效
- **THEN** 页面通过统一 Voice Picker 展示安全裁剪后的 voice ID、名称、口音与类别，并支持关键词、语言、性别筛选和分页加载

#### Scenario: Voice filter options follow account metadata

- **WHEN** ElevenLabs voice 查询成功或当前查询结果刷新
- **THEN** 页面从返回的 voice metadata 动态聚合 Language 和 Gender 可选值，不依赖 Platform 写死枚举；缺失字段统一归入 `Unspecified`，Accent 和 Source/Category 仅在结果卡片展示

#### Scenario: Filter Deepgram voices

- **WHEN** 用户选择 Deepgram Flux 并搜索或筛选音色
- **THEN** 同一个 Voice Picker 在本地 catalog 中按名称/描述关键词、语言与性别即时过滤，并在卡片展示口音和类别

#### Scenario: Voice result set is large

- **WHEN** ElevenLabs 匹配结果超过单页上限
- **THEN** 后端依据 `has_more` 和 `next_page_token` 分页，前端增量加载且保持当前选择不丢失

#### Scenario: Voice list fails

- **WHEN** voice 查询超时、鉴权失败或服务不可用
- **THEN** 页面显示安全错误并保留手工填写 voice ID 的能力
