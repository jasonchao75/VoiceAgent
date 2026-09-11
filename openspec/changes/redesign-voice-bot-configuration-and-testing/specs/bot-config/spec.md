## ADDED Requirements

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

## MODIFIED Requirements

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
