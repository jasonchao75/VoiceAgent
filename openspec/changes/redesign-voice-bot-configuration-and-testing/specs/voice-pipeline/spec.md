## ADDED Requirements

### Requirement: Provider-neutral conversational speed tool

系统 MUST 在 Bot 启用通话内语速控制时向兼容 LLM 注册本地 `set_speech_speed` 工具。LLM MUST 只选择受控 action；当前数值、调整步长、范围校验、provider 调用和结果状态 MUST 由 Pipeline 确定性执行，不得将普通助手文本作为控制 JSON 解析。

#### Scenario: Caller asks the agent to speak faster

- **WHEN** 当前有效 Speed 为 `1.0`、Bot 步长为 `0.10`，且用户明确要求说快一点
- **THEN** LLM 调用 `set_speech_speed(action="faster")`，Pipeline 计算目标 `1.1` 并在成功应用后才允许 LLM 生成确认回复

#### Scenario: Caller asks repeatedly at a provider limit

- **WHEN** 当前 Speed 已达到 provider 上限且用户再次要求加快
- **THEN** Pipeline 返回 `at_limit` 且保持当前值，LLM 不得声称语速继续增加

#### Scenario: Caller resets speed

- **WHEN** LLM 调用 `normal` 或 `configured`
- **THEN** Pipeline 分别以 `1.0` 或该通话启动时的 Bot Speed 为目标，并遵循同一 provider 应用与确认流程

#### Scenario: Tool update fails

- **WHEN** provider 拒绝、超时或连接断开
- **THEN** Pipeline 清除 pending 值、保留之前的 current Speed、返回 `failed`，并确保回复不会宣称修改成功

### Requirement: Session-scoped speed state

系统 MUST 为每次通话独立维护 immutable configured Speed、已生效 current Speed 和可空 pending Speed，并串行化并发更新。临时 Speed 不得覆盖 Bot 持久配置或泄漏到其他通话。

#### Scenario: Change speed twice in one call

- **WHEN** 通话从 configured Speed `0.95` 开始，连续两次成功执行 `faster` 且步长为 `0.10`
- **THEN** current Speed 依次为 `1.05`、`1.15`，第二次基于第一次成功值计算

#### Scenario: End a modified session

- **WHEN** current Speed 与 configured Speed 不同的通话结束，随后同一 Bot 开始新通话
- **THEN** 旧会话状态被销毁，新通话仍从 Bot 保存的 configured Speed 开始

### Requirement: Provider-specific runtime speed application

系统 MUST 通过统一会话工具将 Speed 应用到当前 TTS provider，同时保留现有音频格式、文本聚合、打断和逐轮时延统计契约。

#### Scenario: Apply speed to Flux

- **WHEN** Flux 通话计算出新的合法目标 Speed
- **THEN** 适配器在当前 `/v2/speak` WebSocket 发送 `Configure`，等待有界的成功或失败结果，并从 provider 的下一个 segment 边界采用新值

#### Scenario: Apply speed to ElevenLabs non-v3

- **WHEN** ElevenLabs Flash、Turbo 或 Multilingual 通话计算出新的合法目标 Speed
- **THEN** 适配器在后续文本消息的完整 `voice_settings` 中使用新 Speed，同时保持其他 Voice settings 不变；已缓冲或已生成音频不被重写

#### Scenario: Request speed control with Eleven v3

- **WHEN** 通话使用 Eleven v3 且用户要求改变语速
- **THEN** 系统不得伪造成功或将 prompt pacing 当作数值 Speed；agent 应明确说明当前模型不支持精确通话内语速调整

#### Scenario: Custom LLM rejects tools

- **WHEN** Bot 启用该能力但 Custom OpenAI-compatible endpoint 不支持或拒绝结构化 tool calling
- **THEN** 会话以可诊断错误失败或禁用该能力并明确告知客户端，不得静默解析普通文本来执行控制

### Requirement: Conversational speed diagnostics

系统 MUST 为每次语速控制尝试记录不含敏感信息的 provider、action、旧值、目标值、最终状态和耗时；该事件不得改变既有逐轮 latency 字段或计算公式。

#### Scenario: Inspect a failed speed update

- **WHEN** provider 返回失败或更新超时
- **THEN** 日志或诊断事件能够区分 rejection、timeout、disconnect 与 unsupported，且不包含 API Key 或完整 provider payload
