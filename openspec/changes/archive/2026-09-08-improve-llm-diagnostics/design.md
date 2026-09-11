# Design: Improve LLM Diagnostics

## 1. Diagnostic Flow

新增统一的异步 LLM 探测服务，使用与正式会话相同的 Base URL 规范化、model、Key、超时和 OpenAI-compatible 客户端配置。探测发送固定、无业务数据的最小请求，并以收到首个有效文本增量作为成功标准。

探测必须请求流式 usage，并记录首 Token 时间、总耗时、输出 Token 和 reasoning tokens。探测 Prompt 不要求模型“逐步思考”，避免主动诱发推理。

支持两条入口：

- 已保存 Key 的 Bot：提交 `bot_id`，服务端在内存中解密并测试。
- BYOK Bot：提交 `bot_id` 和本次 LLM Key；Key 只用于本次请求。

不为 Quick start 另建完整配置规则；其诊断可提交与现有 SessionRequest 相同的 LLM 三件套和临时 Key。

OpenAI 与 Custom 使用 OpenAI-compatible 探测；Gemini 使用原生 Google GenerateContent 流式接口。诊断层共享统一结果模型，但不得用 OpenAI-compatible 请求假装验证原生 Gemini adapter。

## 2. Reasoning Control and Evidence

产品层使用 `reasoning_mode: "lowest_latency"` 表达低延迟意图，默认值为 `lowest_latency`。解析顺序固定为：非推理模型不传参数；推理模型优先 `none`，否则 `minimal`，再否则 `low`。第一阶段不提供主动提高思考档位的选项。

Bot 表新增非敏感 `reasoning_mode` 字段并进行幂等迁移；现有 Bot 回填为 `lowest_latency`。SessionConfig 保存该设置与本次实际控制策略，确保 Bot 修改不影响进行中的会话。

适配层根据能力映射请求：

- 已验证为非推理模型：不发送不兼容参数，验证状态可标记为 `not_applicable`。
- 支持 OpenAI Chat Completions `reasoning_effort=none` 的模型：显式发送 `none`。
- 不支持 `none` 但支持 `minimal` 的推理模型：自动发送 `minimal`，标记为 `minimized`，不得显示“已关闭”。
- 连 `minimal` 也不支持但支持 `low` 的模型：自动发送 `low`，同样标记为 `minimized` 并展示实际档位。
- Custom OpenAI-compatible endpoint：只有存在已验证的关闭策略时才发送对应参数；未知实现标记为 `unverified`，不得仅凭无 reasoning 字段推断已关闭。

连通性测试输出以下非敏感证据：

| 字段 | 含义 |
|---|---|
| `reasoning_requested` | 产品配置要求的最低延迟模式 |
| `reasoning_control` | 实际使用的关闭策略或 `none` |
| `reasoning_tokens` | provider usage 返回的数量；未返回为 null |
| `reasoning_content_detected` | 是否观察到 provider 专用 reasoning 内容字段，不保存内容 |
| `reasoning_status` | `confirmed_off`、`not_applicable`、`minimized`、`detected`、`unverified` |

“已确认关闭”要求：关闭参数被接受，且最终 usage 明确报告 `reasoning_tokens=0`，同时未发现 reasoning 内容字段。普通非推理模型显示“不适用（无推理能力）”。任何非零 reasoning tokens 或 reasoning 内容信号均为 `detected`。

OpenAI 通常不返回隐藏思维链正文，因此 UI 只可视化 reasoning token 数量和状态，不展示模型内部思考内容。该规则也避免把敏感推理内容写入日志或历史记录。

## 3. Safe Error Model

内部异常统一映射为有限类别：

| 类别 | 用户含义 | 建议动作 |
|---|---|---|
| `invalid_configuration` | URL 或 model 格式不合法 | 检查配置字段 |
| `authentication_failed` | Key 无效或未授权 | 更换或确认 Key |
| `model_unavailable` | 模型不存在或账号无权限 | 核对模型名与权限 |
| `rate_limited` | 厂商限流或额度限制 | 稍后重试、检查额度 |
| `timeout` | 在配置超时内无响应 | 重试或检查服务状态 |
| `connection_failed` | DNS、TLS 或连接失败 | 检查 Base URL 与网络 |
| `reasoning_minimized` | 模型无法完全关闭，已使用最低档 | 评估实际首 Token 延迟或更换模型 |
| `reasoning_not_disabled` | 检测到高于预期的思考 | 检查能力档案或更换模型 |
| `reasoning_unverified` | provider 不返回足够证据 | 使用已验证模型/endpoint |
| `upstream_error` | 厂商返回其他错误 | 使用 diagnostic_id 关联日志 |

公开响应只包含类别、简短摘要、建议动作、HTTP 状态码（若安全）、provider、Base URL host、model、耗时和随机 `diagnostic_id`。不得返回 URL 中的 query、厂商原始响应体、请求 headers、Prompt 或 Key。

## 4. Runtime Failure Visibility

正式会话的 LLM 异常复用同一分类器。会话级诊断在内存中短暂保留，使前端在 WebSocket 异常结束后仍可凭会话 token 获取安全摘要。保留时间不超过 10 分钟，应用重启可丢失；长期历史由后续 Change 负责。

## 5. Logging and Security

- 日志使用结构化字段记录 `diagnostic_id`、session_id、错误类别、provider、host、model 和异常类型。
- API Key、Authorization header、完整请求/响应体和 Prompt 禁止入日志。
- 已保存 Key 只在探测调用期间解密到内存，并沿用现有 `SecretStr` 与清理约束。
- 探测接口沿用 Demo Basic Auth、Origin 白名单、请求超时和并发限制。
- 日志与历史只保存 reasoning token 数量、控制策略和状态，不保存 reasoning 内容。

## 6. API and UI

- 新增 LLM diagnostic API；请求模型明确区分 Bot saved-key、Bot BYOK 和 Quick start。
- Bot 编辑器与 Quick start 提供 `Test LLM connection` 按钮。
- 测试按钮不隐式保存 Bot，也不修改配置。
- 页面用成功/失败卡片显示诊断结论，真实会话失败时显示相同类别和建议动作。
- Bot 与 Quick start 请求模型新增默认 `lowest_latency` 的 `reasoning_mode`；Bot 响应可返回该非敏感配置。
- UI 在连通性测试结果中展示“Lowest latency requested”、实际档位、reasoning token 数量和验证状态。
- `minimized` 必须展示实际最低档和测得延迟；`detected` 作为偏离预期处理；`unverified` 显示醒目警告并允许用户明确确认后开始会话。

## 7. Provider and Model Capability Catalog

产品下拉框采用“固定已验证资源方 + Custom”模式。固定资源方记录官方 Base URL、推荐模型、Pipecat service/adapter、最低 reasoning 档、关闭参数映射、usage 证据能力和 `verified_at`；Custom 保留手填能力，但不承诺自动识别。

能力档案不能仅通过 `/models` 接口生成，因为常规模型列表通常不声明 `none/minimal/low` 支持范围。维护策略为：官方文档确认 + 最小真实探测验证；未知模型不得按名称猜测，必须显示 `unverified`。

Pipecat 负责请求执行、流式 Frame 和 usage metrics，不作为产品 Catalog 的事实源。当前 1.8.1 `OpenAILLMService.Settings.extra` 可以透传 `reasoning_effort`，并可从流式 usage 提取 `reasoning_tokens`；未来接入 Gemini、Anthropic 等固定资源方时优先使用 Pipecat 对应的专用 Service，而不是强行走 OpenAI-compatible Custom。

首批固定资源方与 Gemini 模型档案：

| Provider | Model | 最低延迟控制 | 状态 | 产品定位 |
|---|---|---|---|---|
| OpenAI | `gpt-4.1-mini` / `gpt-4.1` | 非推理模型，不传 reasoning 参数 | `not_applicable` | 现有稳定选项 |
| OpenAI | `gpt-5-mini` | `reasoning_effort=minimal` | `minimized` | 不能完全关闭 |
| Google Gemini | `gemini-2.5-flash-lite` | `thinking_budget=0` | 待真实验证 `confirmed_off` | Voice Agent 默认推荐 |
| Google Gemini | `gemini-2.5-flash` | `thinking_budget=0` | 待真实验证 `confirmed_off` | 更强质量选项 |
| Google Gemini | `gemini-3.5-flash-lite` | `thinking_level=minimal` | `minimized` | 新一代低成本选项 |
| Google Gemini | `gemini-3.6-flash` | `thinking_level=minimal` | `minimized` | 新一代质量选项 |

“待真实验证”表示参数能力已由官方文档确认，但必须使用用户账号完成一次连通性和 usage 验证后，才能在页面显示最终绿色状态。固定模型 ID 使用具体 stable ID，不使用会自动切换版本的 `latest` alias。

Gemini provider 使用 Pipecat 1.8.1 `GoogleLLMService`：2.5 Flash 系列显式配置 `thinking_budget=0`，3.x Flash 显式配置能力表中的最低 `thinking_level`，`include_thoughts=false`。项目需新增 `pipecat-ai[google]` extra；如果依赖未安装，应用应在启动配置校验阶段给出明确错误，不得运行到通话中才失败。

## 8. Compatibility Notes

当前 Catalog 同时包含 `gpt-4.1*` 和 `gpt-5-mini`：前者按非推理模型处理；当前 OpenAI 官方资料显示旧 GPT-5 系列不支持 `reasoning_effort=none`，最低为 `minimal`，因此 `gpt-5-mini` 默认发送 `minimal` 并显示“已最小化，未完全关闭”。未来更新模型列表时必须同步更新经过官方资料或真实探测验证的能力映射，不能只按模型名前缀猜测。

Gemini 2.5 与 3.x 不能共用同一思考参数：2.5 使用 `thinking_budget`，3.x 使用 `thinking_level`，两者不得同时发送。Pro 模型无法满足当前 Voice Agent 的最低延迟优先策略，第一阶段不进入可选列表；后续需单独验证并经产品确认后才能加入。

## 9. Verification

通过 mock 覆盖全部错误映射、超时、流式首 Token 成功、响应脱敏、日志脱敏、已存 Key/BYOK 两条路径和会话失败展示；真实付费 API 验证只在用户明确确认后执行。

额外覆盖非推理模型、支持 `none`、最低为 `minimal`、最低为 `low`、reasoning tokens 非零、usage 缺失和 provider 专用 reasoning 字段。
