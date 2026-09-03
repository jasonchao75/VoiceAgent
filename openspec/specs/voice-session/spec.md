# Voice Session Specification

## Purpose

定义浏览器语音会话的创建、授权、配置校验、生命周期和密钥安全行为。

## Requirements

### Requirement: Session creation modes

系统必须支持 Quick start 内联配置创建会话，以及通过已存在的 Bot 配置创建会话。两种配置模式不得在同一个请求中混用。

#### Scenario: Create a Quick start session

- **WHEN** 客户端提交完整的内联配置和当次使用的 Deepgram、LLM API Key
- **THEN** 系统创建待连接会话，并返回单次使用的会话令牌

#### Scenario: Create a session from a Bot

- **WHEN** 客户端提交有效 `bot_id`，并按照 Bot 的密钥模式提供所需凭据
- **THEN** 系统使用 Bot 配置快照创建会话，后续修改 Bot 不影响该会话

### Requirement: Session token lifecycle

会话令牌必须具有有限有效期、只能成功认领一次，并绑定到单个 WebSocket 会话。

#### Scenario: Reuse a claimed token

- **WHEN** 客户端再次使用已经成功认领的令牌
- **THEN** 系统拒绝连接

#### Scenario: Pending token expires

- **WHEN** 待连接令牌超过配置的有效期
- **THEN** 系统删除待连接会话并清除其凭据引用

### Requirement: Session configuration validation

系统必须使用服务器 Catalog 校验公开的 voice、LLM provider 和非 custom provider 的 base URL；非本机来源创建 BYOK 会话时必须使用允许的 HTTPS Origin。

#### Scenario: Submit an unknown voice

- **WHEN** 客户端提交不在服务器 Voice Catalog 中的 voice
- **THEN** 系统拒绝创建会话

### Requirement: Session secret safety

API Key 明文不得出现在 API 响应、校验错误、日志或会话配置中；会话结束、过期或应用关闭时必须清除内存凭据引用。

#### Scenario: Request validation fails

- **WHEN** 包含 API Key 的会话请求校验失败
- **THEN** 错误响应只返回安全的字段位置和错误类型，不回显被拒绝的输入

### Requirement: Session telemetry authorization

会话事件接口必须使用当前会话的 Bearer token 独立鉴权，不得把 Bearer token 交给页面 Basic Auth 校验，也不得在 token 失效时返回 Basic Auth challenge。

#### Scenario: Telemetry token is invalid

- **WHEN** 浏览器使用无效或过期的会话 Bearer token 请求事件接口
- **THEN** 系统返回会话鉴权错误且不包含 `WWW-Authenticate: Basic`，浏览器不会因此重新弹出登录框
