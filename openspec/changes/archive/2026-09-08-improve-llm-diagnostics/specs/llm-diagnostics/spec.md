# Delta: LLM Diagnostics

## Purpose

让用户无需访问服务器日志即可验证 LLM 配置，并获得安全、可行动的运行时错误诊断。

## ADDED Requirements

### Requirement: User-triggered LLM connectivity test

系统必须允许用户从 Bot 编辑器或 Quick start 主动测试当前 LLM Base URL、model 和 Key 能否产生最小流式响应。系统不得在用户未操作时自动发起测试。

#### Scenario: Connectivity test succeeds

- **WHEN** 用户确认可能产生少量厂商费用并点击测试，且服务收到首个有效文本增量
- **THEN** 页面显示成功、实际 provider/host/model 和服务端观测耗时

### Requirement: Actionable diagnostic categories

系统必须把 LLM 测试和正式会话的常见失败映射为有限、安全且可行动的错误类别。

#### Scenario: Configured model is unavailable

- **WHEN** 厂商明确返回模型不存在或当前账号无权使用
- **THEN** 页面显示 `model_unavailable`、核对模型的建议和 `diagnostic_id`

#### Scenario: Provider response is ambiguous

- **WHEN** 厂商错误无法安全、可靠地归入具体类别
- **THEN** 页面显示 `upstream_error`，不得把原始响应体直接返回浏览器

### Requirement: Diagnostic secret safety

诊断请求和结果不得把 API Key、Authorization header、Prompt、完整厂商响应体或带 query 的 URL 写入日志、响应、数据库或浏览器存储。

#### Scenario: Diagnostic request fails

- **WHEN** 携带 LLM Key 的测试请求失败
- **THEN** 响应只包含脱敏诊断字段，任何位置不出现 Key

### Requirement: Runtime LLM failure visibility

正式语音会话发生 LLM 错误时，用户必须能在页面查看与连通性测试一致的安全诊断类别和建议动作。

#### Scenario: Voice session LLM call times out

- **WHEN** LLM 在配置的超时时间内没有响应并导致会话失败
- **THEN** 页面显示 `timeout` 和对应 `diagnostic_id`，无需登录服务器查日志

### Requirement: Lowest-latency reasoning by default

Bot 和 Quick start 必须默认使用 LLM 支持的最低思考档。系统必须根据经过验证的 provider/model 能力依次选择 `none`、`minimal`、`low`，不得向不支持该参数的非推理模型盲目透传。

#### Scenario: Model supports explicit reasoning disable

- **WHEN** 用户使用支持关闭思考的模型创建测试或正式会话
- **THEN** 系统显式发送对应关闭参数，并在配置快照中记录关闭意图与控制策略

#### Scenario: Reasoning model cannot use none

- **WHEN** 所选推理模型不支持 `none` 但支持 `minimal`
- **THEN** 系统默认发送 `minimal` 并显示 `minimized` 与实际档位，不得标记为已关闭思考

### Requirement: Reasoning evidence in connectivity test

LLM 连通性测试必须请求并展示非敏感 reasoning 证据，包括实际关闭策略、reasoning token 数量和验证状态。系统不得展示或持久化隐藏思维链正文。

#### Scenario: Provider confirms zero reasoning tokens

- **WHEN** 关闭参数被接受、usage 明确返回 `reasoning_tokens=0`，且未检测到 reasoning 内容字段
- **THEN** 页面显示 `confirmed_off` 和 reasoning tokens 为 0

#### Scenario: Provider returns reasoning tokens

- **WHEN** usage 返回的 reasoning tokens 大于 0，或响应出现 provider 专用 reasoning 内容字段
- **THEN** 页面显示 `detected`、实际 token 数量（若提供）和延迟风险告警

#### Scenario: Provider does not expose reasoning evidence

- **WHEN** Custom endpoint 未返回 reasoning usage，且没有已验证的关闭能力映射
- **THEN** 页面显示 `unverified`，不得把缺少字段解释为 reasoning tokens 为 0，并要求用户明确确认风险后才能继续通话

#### Scenario: User accepts unverified reasoning risk

- **WHEN** Custom endpoint 的状态为 `unverified`，且用户明确确认可能存在额外首 Token 延迟
- **THEN** 系统允许本次通话并保留 `unverified` 状态，不得改写为 `confirmed_off`

### Requirement: Runtime reasoning monitoring

正式语音会话必须逐轮采集 provider 返回的 reasoning token 数量和验证状态；检测到非零 reasoning tokens 时必须向页面告警。

#### Scenario: Reasoning unexpectedly appears during a call

- **WHEN** 连通性测试曾确认关闭，但正式会话某轮返回非零 reasoning tokens
- **THEN** 页面显示该轮 reasoning 数量与告警，历史指标 Change 生效后同时保存该非敏感证据

### Requirement: Verified provider and model catalog

系统必须为固定资源方维护经过官方资料或真实探测验证的模型能力档案，包括最低 reasoning 档、参数映射、usage 证据能力和验证日期，同时保留 Custom 入口。

#### Scenario: User selects a verified model

- **WHEN** 用户从固定资源方选择经过验证的模型
- **THEN** 系统自动应用该模型的最低 reasoning 档和正确参数，无需用户理解厂商差异

#### Scenario: User enters an unknown custom model

- **WHEN** Custom endpoint/model 没有已验证能力档案
- **THEN** 系统执行连通性测试并显示 `unverified`；用户明确确认警告后可以继续

### Requirement: Native Gemini provider

系统必须把 Google Gemini 作为固定资源方，通过 Pipecat `GoogleLLMService` 和原生 Gemini API 执行诊断与正式会话。用户选择 Gemini 时不得要求手填 Base URL。

#### Scenario: Select Gemini for a Bot

- **WHEN** 用户在 Bot 编辑器选择 Google Gemini
- **THEN** 页面显示固定模型下拉框和 Gemini API Key，不显示可编辑 Base URL，并使用同一原生 adapter 完成测试与会话

### Requirement: Model-specific Gemini thinking control

系统必须区分 Gemini 2.5 的 `thinking_budget` 与 Gemini 3.x 的 `thinking_level`，根据固定能力档案应用最低延迟设置，且不得在同一请求中同时发送两类参数。

#### Scenario: Use Gemini 2.5 Flash

- **WHEN** 用户选择 `gemini-2.5-flash` 或 `gemini-2.5-flash-lite`
- **THEN** 系统发送 `thinking_budget=0` 和 `include_thoughts=false`，并通过真实 usage 证据判断是否 `confirmed_off`

#### Scenario: Use Gemini 3.x Flash

- **WHEN** 用户选择固定 Catalog 中的 Gemini 3.x Flash 模型
- **THEN** 系统发送该模型支持的最低 `thinking_level`，显示 `minimized` 与实际档位，不得显示完全关闭

### Requirement: Stable Gemini model IDs

固定 Gemini Catalog 必须使用经过验证的具体 stable model ID 和验证日期，不得使用可能自动切换底层版本的 `latest` alias。

#### Scenario: Gemini catalog is updated

- **WHEN** Agent 新增或替换固定 Gemini model ID
- **THEN** 同步核对官方模型状态、思考参数、Pipecat adapter 和真实连通性，并更新 `verified_at`
