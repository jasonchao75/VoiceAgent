# Improve LLM Diagnostics

## Why

用户配置 LLM Base URL、Model 和 API Key 后，经常只能看到“调用失败”，无法判断是地址、模型、Key、超时、限流还是厂商故障。当前详细信息主要存在服务器日志中，产品经理没有方便、安全的自助排查入口。

Voice Agent 对首 Token 延迟高度敏感，但当前也无法确认所选模型是否启用了隐藏推理。某些推理模型默认会消耗 reasoning tokens，且不同 provider/model 用于关闭思考的参数并不完全一致。

## What Changes

- 在 Bot 编辑页增加用户主动触发的 LLM 连通性测试。
- 对配置校验和真实会话中的 LLM 故障进行分类，向页面返回脱敏、可行动的诊断结果。
- 为每次诊断生成 `diagnostic_id`，便于关联页面提示与服务器日志。
- 页面展示实际使用的 provider、Base URL host、model、阶段、耗时和安全错误摘要，不显示 API Key、完整上游响应或敏感请求内容。
- 为已存 Key Bot 和会话级 BYOK Bot 分别支持安全测试。
- Bot 与 Quick start 增加“最低思考延迟”配置并默认启用；后端按已验证的 provider/model 能力优先使用 `none`，不支持 `none` 时自动使用最低可用档（依次为 `minimal`、`low`）。
- 连通性测试同时展示关闭参数是否被接受、返回的 reasoning token 数量和“已确认关闭 / 检测到思考 / 无法验证”状态。
- 正式会话逐轮采集 reasoning token 数量；发现非零 reasoning tokens 时在页面明确告警。
- 将 Google Gemini 纳入首批固定资源方，使用 Google 原生 Gemini API 与 Pipecat `GoogleLLMService`，不再要求用户把 Gemini 当作 Custom 手填 Base URL。
- Gemini 固定模型优先提供可完全关闭思考的 2.5 Flash-Lite/Flash，并提供只能最小化思考的 3.x Flash 选项及明确状态。

## Out of Scope

- 不做代理厂商控制台、余额查询或完整日志管理系统。
- 不自动更换 Base URL、model 或 Key。
- 不保存或回显 API Key。
- 不保证判断厂商账号余额、模型权限等所有业务原因；厂商未提供明确错误时标记为 `upstream_error`。
- 不在后台自动发起付费测试；只有用户点击测试时才发送最小请求。
- 不展示或保存模型隐藏思维链；只展示厂商返回的 reasoning token 数量、是否出现 reasoning 内容字段及验证结论。
- 不把“不返回 reasoning usage”解释为零思考；证据不足时必须标记为“无法验证”。

## Success Criteria

- 用户无需登录服务器，即可在页面确认配置是否能完成一次最小 LLM 流式响应。
- 常见失败可区分为配置错误、鉴权、模型不存在/无权限、限流、超时、网络连接和未知上游错误。
- 会话运行期的 LLM 失败在页面显示安全错误类别、建议动作和 `diagnostic_id`。
- 测试和错误响应、日志、数据库及浏览器存储中均不出现 API Key。
- 普通语音会话行为与已有 BYOK/Bot Key 生命周期不回归。
- 用户选择 Gemini 后只需选择固定模型并填写 Gemini API Key，不需要填写 Base URL；连通性测试与正式会话使用同一个原生 Gemini adapter。
- 新建 Bot 和 Quick start 默认使用模型允许的最低思考档；无法完全关闭时必须明确显示实际档位，不得显示“已关闭”。
- 连通性测试返回 `reasoning_tokens=0` 且关闭参数被 provider 接受时，页面显示“已确认关闭”；返回非零时显示实际数量和延迟风险；provider 不返回可验证证据时显示“无法验证”。
- Custom endpoint 为“无法验证”时，用户可在明确确认延迟风险后继续通话；系统必须保留本次确认状态，不得把它展示为“已关闭”。

## Dependencies and Delivery

- 本 Change 先于 `add-call-history-and-metrics` 实现。
- 两个 Change 可以在同一版本部署；历史通话 Change 将复用这里定义的错误类别和 `diagnostic_id`。
- 连通性测试会产生一次极小的真实 LLM 请求，页面必须在用户点击前明确提示可能产生少量厂商费用。
- Gemini 原生接入需要把 Pipecat 的 `google` extra（包含 `google-genai`）加入生产依赖；实现前需按项目规则确认新增依赖。
