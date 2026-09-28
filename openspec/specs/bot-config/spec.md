# Bot Configuration Specification

## Purpose

定义单实例 VoiceAgent Demo 中 Bot 配置的持久化、加密密钥保存、能力目录校验、管理接口、产品登录保护及 provider 降级行为。

## Requirements

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

### Requirement: Bot key update semantics

更新 Bot 时 MUST 支持保留、替换和清除已保存 Key。Deepgram Key 与 LLM Key 始终必须同时存在或同时为空；ElevenLabs Key 只在当前 TTS provider 为 ElevenLabs 时参与凭证齐备性判断。

#### Scenario: Edit configuration without submitting keys

- **WHEN** 用户修改已保存 Key 的 Bot 配置但不提交新 Key
- **THEN** 系统保留原有加密 Key

#### Scenario: Switch away from ElevenLabs without clearing its key

- **WHEN** 用户将 TTS provider 从 ElevenLabs 切换为 Deepgram Flux 且未显式清除 Key
- **THEN** 系统可保留已加密的 ElevenLabs Key，但 `has_saved_keys` 只按 Deepgram 和 LLM Key 计算

### Requirement: Approved prototype conformance

Bot 编辑器、Test bot 二级页面和 Sessions 详情 MUST 遵循本 Change 已确认的 `prototypes/index.html` 与 `prototypes/README.md`。行为和数据规则以 Delta Specs 为准；布局、分组、选中/收起状态、就近指标和响应式行为以原型为 UI baseline。原型中的示例 latency 与 `Simulate caller turn` MUST NOT 进入生产。

#### Scenario: Implement the approved Bot editor

- **WHEN** 开发完成 Bot editor
- **THEN** ASR/LLM/TTS 卡片、非模态抽屉、字段归属、provider 联动、Voice Picker、Thinking、Conversational speed、凭证门禁和响应式布局与原型一致

#### Scenario: Prevent a simplified voice selector regression

- **WHEN** 开发或后续修改 Voice selector
- **THEN** 自动化 UI 检查和验收截图确认搜索、能力驱动筛选、已选音色摘要，以及 provider catalog 需要时的分页均可用
- **AND** Custom voice ID 只对明确支持它的 provider 展示，Deepgram Flux 不得展示该入口

#### Scenario: Switch between TTS providers

- **WHEN** 用户在 Deepgram Flux 与 ElevenLabs 之间切换
- **THEN** Model、Key、Voice Library、Speed 范围和 Advanced 字段完整切换，不保留另一 provider 的陈旧状态

#### Scenario: Implement the approved test and history experience

- **WHEN** 开发完成 Chat test、Web call test 和 Sessions
- **THEN** 生命周期按钮、字幕、barge-in、Agent 回复下方逐 Turn 指标、列表 View 和可收起详情抽屉与原型一致

#### Scenario: Prevent fabricated prototype behavior

- **WHEN** 生产页面显示 latency 或处理 Web call 用户输入
- **THEN** latency 必须来自真实探针且 Web call 必须使用麦克风，不得使用原型示例值或 simulation 按钮

#### Scenario: Open the Advanced tab in this release

- **WHEN** 用户点击顶层 `Advanced`
- **THEN** 页面仅展示当前 Bot 的 LLM timeout Fallback script 配置，其余高级能力由后续 Change 承接

#### Scenario: Pass Gate 1 before UI implementation

- **WHEN** 团队准备实现或继续修改本 Change 的页面
- **THEN** Delta Specs、原型、精确标注、状态矩阵、固定 fixture 与 baseline 必须先完成映射并由用户确认，未确认时不得继续核心页面实现

#### Scenario: Review the static shell at Gate 2

- **WHEN** 页面壳、布局、抽屉和基础控件形态完成但业务逻辑尚未全部接入
- **THEN** 团队必须用固定视口截图对照已确认 baseline，先获得整体布局与视觉方向确认，不得以静态字符串测试代替

#### Scenario: Submit Gate 3 evidence

- **WHEN** 页面业务逻辑和状态覆盖完成并准备最终验收
- **THEN** Change 内必须保存 baseline、实际截图、diff、差异比例、测试环境、功能与可访问性结果、已知差异及结论；自动检查不得替代用户最终验收

#### Scenario: Handle an intentional visual deviation

- **WHEN** 实现需要有意偏离已确认原型或 baseline
- **THEN** 团队必须先登记偏离原因、更新 Change 与 baseline 候选并重新获得用户确认，测试不得静默覆盖原 baseline

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

### Requirement: Deepgram Flux voice tuning

系统 MUST 允许用户按 Bot 配置 Deepgram Flux `expressivity` 与 `speed`，保存后再次编辑必须完整回显。现有 Bot 必须保持 `expressivity=0`、`speed=1.0` 的既有声音行为。

#### Scenario: Configure a more expressive Flux voice

- **WHEN** 用户选择 Deepgram Flux，将 Expressivity 设为 `1`，并将 Speed 设为 `1.05`
- **THEN** Bot 保存两个值，页面再次打开时回显相同配置，后续会话使用相同配置

#### Scenario: Reject invalid Flux controls

- **WHEN** Expressivity 不是 `-2..2` 的整数，或 Speed 不在 `0.5..1.5` 的 `0.05` 步长内
- **THEN** API 拒绝保存，不得静默截断或修正

#### Scenario: Edit a legacy Bot

- **WHEN** 数据库中的旧 Bot 没有 Expressivity 字段
- **THEN** 系统迁移为 `0`，并保留既有 Speed；声音行为不发生隐式变化

### Requirement: Product-owned login experience

系统 MUST 使用 VoiceAgent 自有登录页保护生产演示站，并在登录成功后用安全 Cookie 维持网站登录状态。系统 MUST 保持网站登录与单次 Chat/Web call 的 Bearer Token 相互独立。任何页面 API、会话事件或会话指标请求失败时均不得返回 Basic Auth challenge 或触发浏览器原生登录弹窗。

面向用户的平台名称 MUST 全局统一为 `VoiceAgent Demo`。登录页 MUST 与平台已确认的深色视觉、绿色强调、字体层级、间距、控件和响应式风格一致，不得显示 `Flux Agent Platform`、`Flux Voice Lab` 等历史名称，也不得使用脱离平台风格的通用登录模板。

#### Scenario: Open a protected page while signed out

- **WHEN** 用户未登录或网站登录已过期，并打开任意受保护页面
- **THEN** 系统展示 VoiceAgent 登录页，不展示浏览器原生登录弹窗
- **AND** 登录成功后返回用户原本准备访问的站内位置

#### Scenario: View consistent product identity

- **WHEN** 用户查看登录页、浏览器标题或登录后的主界面品牌区域
- **THEN** 用户可见平台名称均为 `VoiceAgent Demo`，且登录页视觉与主界面属于同一设计体系

#### Scenario: Use Chat test after signing in

- **WHEN** 已登录用户开始 Chat test，页面使用单次会话 Bearer Token 读取 events 或 metrics
- **THEN** 网站登录保持有效，Turn 指标正常返回，浏览器不再次要求输入网站用户名和密码

#### Scenario: Submit invalid login credentials

- **WHEN** 用户提交错误用户名或密码
- **THEN** 页面显示不区分用户名或密码的通用失败提示，不泄露凭证、不刷新为浏览器原生弹窗

#### Scenario: Website login expires

- **WHEN** 网站登录过期且用户进行下一次页面操作
- **THEN** 页面进入登录页并说明登录已过期；重新登录后返回原站内位置

#### Scenario: Sign out

- **WHEN** 用户在左侧栏底部 hover/focus 用户头像，或在触屏设备点击头像
- **THEN** 页面显示 `Log out` 操作，且折叠/展开侧栏和窄屏均可使用
- **WHEN** 用户点击 `Log out`
- **THEN** 网站登录会话立即失效并返回登录页，后续受保护请求不能继续使用旧 Cookie

### Requirement: Componentized Bot editor

系统 MUST 将 Bot-owned 配置与 provider-owned 配置分离。Bot settings 主页面 MUST 只保留 Bot 名称、Opening message 和 System prompt；ASR、LLM、TTS 参数及凭证 MUST 分别进入对应组件的非模态右侧抽屉。抽屉打开时 MUST 压缩主工作区而不是使用阻塞遮罩。

#### Scenario: Open and collapse a component drawer

- **WHEN** 用户点击 ASR、LLM 或 TTS 卡片
- **THEN** 对应卡片显示选中状态，右侧抽屉打开并压缩主区域；再次点击同一卡片或收起按钮时恢复原布局

#### Scenario: Keep Bot settings provider-neutral

- **WHEN** 用户查看 Bot settings 主页面
- **THEN** 页面不显示 provider 参数、API Key 或重复的 Primary language，组件卡片也不展示无历史测量来源的 latency

#### Scenario: View current navigation scope

- **WHEN** 用户查看产品栏和顶部 Tab
- **THEN** 产品栏仅包含可收缩的 VoiceAgent，顶部包含 Bot settings、Sessions、Advanced；Advanced 仅展示当前 Bot 的 LLM timeout Fallback script，且不出现 Evaluation、账户、SIP line、说话顺序或 Prompt 自动生成入口

### Requirement: ASR options come from a server capability catalog

系统 MUST 由后端 `/api/catalogs` 提供 ASR provider、model 与 model-specific language 能力，前端不得硬编码或展示 catalog 未返回的组合。本期仅提供 Deepgram / Flux ASR，以及映射到 `flux-general-en` 和 `flux-general-multi` 的 English 与 Automatic。

#### Scenario: Load current Flux ASR options

- **WHEN** Bot 编辑器成功读取 ASR capability catalog
- **THEN** Provider 仅显示 Deepgram，Model 仅显示 Flux ASR，Language 仅显示 English 与 Automatic

#### Scenario: Fail to load ASR capabilities

- **WHEN** catalog 请求失败
- **THEN** Model 与 Language 保持禁用并提供重试提示，不得回退到前端虚构选项

### Requirement: Current WebCall input format

系统 MUST 将本期 WebCall 输入保持为 mono Linear16 PCM 16 kHz，并只展示只读能力信息。在独立传输/重采样 Change 前不得提供 8 kHz 选项。

#### Scenario: View current WebCall audio input

- **WHEN** 用户打开 Flux ASR 配置
- **THEN** 页面只展示 `PCM · 16 kHz`，不展示 8 kHz 选项

### Requirement: Persist Flux ASR settings per Bot

系统 MUST 按 Bot 保存 Flux ASR model、可选 language hints、EOT threshold、EOT timeout、keyterms、profanity filter、numerals 与 redact。会话 MUST 使用 Bot 快照，禁止读取全局 Runtime ASR 业务配置。本期不得暴露 Eager EOT。

#### Scenario: Configure Automatic language detection

- **WHEN** 用户选择 Automatic，并选择零个或多个 language hints
- **THEN** 保存 `flux-general-multi` 与完整 hints；空列表表示在官方支持的十种语言中自动检测

#### Scenario: Configure Flux business parameters

- **WHEN** 用户保存合法 threshold、timeout、keyterms、filter、numerals 与 redact
- **THEN** Bot 完整回显，并在新会话建连或 provider 允许的 Configure 时点使用对应参数

#### Scenario: Enter keyterms with spaces

- **WHEN** 用户逐行输入 `Riyad Bank` 或 `customer service`
- **THEN** 系统保存未转义文本并负责 provider 编码；用户无需输入 `%20`

#### Scenario: Reject unsupported ASR combinations

- **WHEN** English model 携带 hints、keyterms 超过 100 条、数值越界或 redact 不受支持
- **THEN** API 返回字段级错误且不保存

#### Scenario: Show only supported Flux ASR Advanced controls

- **WHEN** 用户打开 Flux ASR Advanced
- **THEN** 页面依次展示 EOT threshold 拖拽条、EOT timeout 数值输入、Keyterms 逐行文本框、Profanity filter 开关、Numerals 开关和 Redact 单选下拉框
- **AND** 页面不展示 Eager EOT、Nova endpointing、smart detection 或 noise suppression

#### Scenario: Enter a component API Key without enabling persistence

- **WHEN** 用户打开 ASR、LLM 或 TTS 组件抽屉
- **THEN** 对应组件的 API Key 输入框默认可填写，保存 Key 的选择只决定是否加密持久化，不得控制输入框是否可用
- **AND** 每个组件只展示和使用自己的 Key，不得出现其他组件的凭证

### Requirement: LLM Thinking override and connection diagnostic

LLM drawer MUST 在基础配置中提供并按 Bot 保存 `0.0`–`2.0` 的 Temperature。LLM Advanced MUST 提供 Provider default、Off、Minimal 三种 Thinking override，以及按 Bot 保存的 Max response tokens 与 Request timeout。Custom OpenAI-compatible Model 可自由输入，前端 MUST NOT 根据 model 字符串猜测能力。系统 MUST 使用当前未保存配置执行 LLM diagnostic 并返回真实 TTFT。

#### Scenario: Use provider-default thinking

- **WHEN** 用户选择 Provider default
- **THEN** 请求不发送 Thinking override，由 endpoint/model 使用自身默认行为

#### Scenario: Test an explicit thinking override

- **WHEN** 用户选择 Off 或 Minimal 并点击 Test LLM connection
- **THEN** 系统使用当前 Base URL、Model、Key 和 override 发起测试，不保存 Bot，并显示连通结果、实测 TTFT 或安全的不兼容错误

#### Scenario: Keep streaming implicit

- **WHEN** 用户打开 LLM Advanced
- **THEN** 页面不展示 Streaming 开关，运行时继续使用平台默认 streaming 行为

#### Scenario: Time out an LLM turn

- **WHEN** LLM 在 Bot 配置的 Request timeout 内未完成
- **THEN** 系统取消该次生成并通过 TTS 播报该 Bot 的 Fallback script，不得再次请求 LLM

### Requirement: Provider-dependent TTS configuration

TTS drawer MUST 将基础字段保持到 Initial speed，并在其后使用一个 Advanced，顺序为 Text aggregation、Conversational speed control、provider-specific tuning。切换 provider MUST 同步替换 model、credential、Voice Library、Speed 范围和 Advanced 字段。

#### Scenario: Browse ElevenLabs account voices

- **WHEN** provider 为 ElevenLabs 且尚未提供 Key
- **THEN** Voice Library 与 Custom voice ID 暂不可用并提示先输入 Key；提供 Key 后加载账户音色并允许两种选择方式

#### Scenario: Browse Deepgram Flux voices

- **WHEN** provider 为 Deepgram Flux
- **THEN** 用户无需预先填写 Key 即可筛选和选择官方 Flux 音色，页面不展示 Custom voice ID，并展示 Flux speed 与 provider Advanced

#### Scenario: Filter and identify voices

- **WHEN** 用户搜索或选择语言/口音、性别筛选
- **THEN** 页面即时过滤当前 provider 的音色，并以名称首字母自动生成列表与已选音色头像

### Requirement: Conversational speed-control configuration

系统 MUST 允许按 Bot 启用通话内语速控制，并配置每次 `faster`/`slower` 的步长。现有 Bot 默认关闭且保留已保存 Initial speed。

#### Scenario: Enable conversational speed control

- **WHEN** 用户为支持的 TTS model 启用并设置 `0.15`
- **THEN** Bot 保存启用状态和步长，新通话据此注册本地 LLM 工具

#### Scenario: Reject an invalid adjustment step

- **WHEN** 步长不在 `0.05`–`0.25` 或不符合 `0.05` 增量
- **THEN** API 返回字段级错误，不保存也不静默修正

#### Scenario: Migrate an existing Bot

- **WHEN** 旧 Bot 缺少字段
- **THEN** 迁移为 `tts_dynamic_speed_enabled=false`、`tts_speed_step=0.10`，并保持 `tts_speed`

#### Scenario: Select Eleven v3

- **WHEN** 用户选择 Eleven v3
- **THEN** 页面禁用通话内语速控制和步长，API 拒绝保存启用状态并明确模型限制

### Requirement: Current Deepgram Flux speed range

系统 MUST 使用当前 Flux `/v2/speak` 契约校验 Initial speed 与通话内 speed，有效范围为 `0.5`–`1.5`、步长 `0.05`。

#### Scenario: Configure the supported range

- **WHEN** 用户保存合法 Flux speed
- **THEN** Bot 完整保存/回显并在后续会话使用；非法值被字段级拒绝

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
