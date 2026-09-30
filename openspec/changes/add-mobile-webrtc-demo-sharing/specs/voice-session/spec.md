# Voice Session Delta Specification

## ADDED Requirements

### Requirement: Public mobile session admission

系统 MUST 允许未登录访客通过有效 Demo Link 为其绑定的 Published Bot 创建 `mobile_web_call` Session。公开请求不得接受 Bot ID、Provider 配置或 API Key 覆盖；系统 MUST 仅使用最后一次成功发布的不可变 Bot 配置快照和服务器保存的组件凭证，不得读取未发布草稿，并复用当前最多 3 路并发限制。

公开 Session MUST 按发布快照中的 component+provider 引用读取该 Bot 当前加密凭据。同 Provider Key 轮换必须立即生效；未发布的 Provider 草稿切换不得改变解析目标；缺失任一被引用凭据时不得创建 Session。

#### Scenario: Start from an active Demo Link

- **WHEN** 访客在允许的 HTTPS Origin 中通过有效且启用的 Demo Link 点击 Start voice call
- **THEN** 系统创建短时、单次的 `mobile_web_call` Lease，并返回不暴露 Bot 配置或 Provider Key 的 WebRTC connection URL

#### Scenario: Start while the Bot has unpublished changes

- **WHEN** Demo Link 有效但 Bot 草稿已在上次发布后修改
- **THEN** 新 Session 继续使用上次成功发布的 revision，不读取草稿值

#### Scenario: Reject an inactive public entry

- **WHEN** Demo Link 不存在、已停用、Bot 未发布、Bot 已删除或发布配置缺少有效凭证
- **THEN** 系统不创建 Session，并返回适合公开页面展示的安全错误分类

#### Scenario: Reject public configuration overrides

- **WHEN** 公开会话请求携带 `bot_id`、Provider、model、Prompt、voice 或任何 API Key
- **THEN** 系统拒绝请求，不使用也不回显这些字段

#### Scenario: Public capacity is full

- **WHEN** 当前 pending 与 active Session 已达到 3 路上限
- **THEN** 系统返回忙碌分类，移动页提示稍后重试且不暴露内部容量配置

### Requirement: Single-use Small WebRTC connection

`mobile_web_call` MUST 使用 Pipecat Small WebRTC 传输。连接 URL MUST 包含短时、不可预测、只能成功认领一次的会话能力；服务端只在合法 SDP offer 认领成功后创建对应 `SmallWebRTCConnection` 与 Pipeline task，并在失败、超时、断开或结束后释放 ICE、媒体、凭证和 Session 资源。

#### Scenario: Complete WebRTC negotiation

- **WHEN** 移动客户端使用未过期 connection URL 提交合法 SDP offer 并完成 ICE
- **THEN** 服务端把该连接绑定到唯一 Lease，客户端进入 Connected 后才开始计时和播放 Opening Message

#### Scenario: Reuse a claimed connection URL

- **WHEN** 第二个请求重复使用已认领或已结束的 connection URL
- **THEN** 系统拒绝连接且不得启动第二个 Pipeline

#### Scenario: Negotiation expires

- **WHEN** 访客获得 connection URL 后未在短时有效期内完成认领
- **THEN** 系统清理 pending Lease 和凭证引用，不创建历史中的虚假完成通话

#### Scenario: WebRTC media disconnects

- **WHEN** ICE/PeerConnection 在通话中断开且有界恢复未成功
- **THEN** 系统取消生成和播放、完成安全错误历史、释放连接并允许用户通过 Retry 创建新 Session

### Requirement: Transport-specific session compatibility

系统 MUST 保留现有 `web_call` 与 `chat_test` WebSocket 路径；新增 `mobile_web_call` 只替换浏览器与 Pipeline 之间的 Transport，不改变 Bot 配置快照、ASR/LLM/TTS、Opening Message、打断、语速控制、历史或指标契约。

#### Scenario: Run existing WebSocket tests after WebRTC addition

- **WHEN** 已登录用户启动现有 Chat test 或 Web call test
- **THEN** 请求、WebSocket 连接、会话类型和用户体验保持兼容

#### Scenario: Run a mobile WebRTC call

- **WHEN** 公开客户端完成 WebRTC 连接
- **THEN** 输入音频通过 Small WebRTC transport 进入同一 Pipeline，输出音频和 transport messages 返回同一 PeerConnection
