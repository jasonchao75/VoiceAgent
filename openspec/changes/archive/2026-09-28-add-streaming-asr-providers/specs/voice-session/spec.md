# Voice Session Delta Specification

## MODIFIED Requirements

### Requirement: Session creation modes

系统必须支持 Quick start 内联配置创建会话，以及通过已存在的 Bot 配置创建会话；两种配置模式不得在同一个请求中混用。系统 MUST 根据 Bot ASR Provider 解析对应的会话级 ASR 凭证和不可变配置快照；Chat Test 继续绕过 ASR，Web Call 必须具备当前 Provider 的有效凭证。

#### Scenario: Create a Quick start session

- **WHEN** 客户端提交完整的内联配置和当次使用的 ASR、LLM 及所选 TTS Provider API Key
- **THEN** 系统创建待连接会话，并返回单次使用的会话令牌

#### Scenario: Create a session from a Bot

- **WHEN** 客户端提交有效 `bot_id`，并按照 Bot 的密钥模式提供所需凭据
- **THEN** 系统使用 Bot 配置快照创建会话，后续修改 Bot 不影响该会话

#### Scenario: Create an AssemblyAI Web Call session

- **WHEN** Bot 选择 AssemblyAI 且当前会话具备有效 AssemblyAI ASR Key
- **THEN** Session Lease 保存非明文凭证引用和 `universal-3-5-pro` 配置快照，不要求 Deepgram ASR Key

#### Scenario: Start without current provider credential

- **WHEN** 当前 ASR Provider 没有临时或已保存 Key
- **THEN** 系统拒绝启动 Web Call，返回当前组件缺凭证的安全错误

### Requirement: Session secret safety

ASR、TTS、LLM 凭证 MUST 按组件和 Provider 清晰归属；会话结束、过期或应用关闭时必须清除所有明文引用，日志和 API 响应不得泄露任何 Provider Key。

#### Scenario: Request validation fails

- **WHEN** 包含 API Key 的会话请求校验失败
- **THEN** 错误响应只返回安全的字段位置和错误类型，不回显被拒绝的输入

#### Scenario: Provider rejects an ASR credential

- **WHEN** 任一 ASR Provider 返回鉴权错误
- **THEN** 系统返回统一安全分类，日志可记录 Provider 和请求标识但不包含 Key 或完整原始 payload
