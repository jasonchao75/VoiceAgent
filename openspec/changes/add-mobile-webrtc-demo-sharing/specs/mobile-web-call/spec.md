# Mobile Web Call Delta Specification

## ADDED Requirements

### Requirement: Public mobile demo entry

系统 MUST 提供无需 VoiceAgent 后台登录的单 Bot 移动通话页。页面只显示已发布的公开标题、介绍和 VoiceAgent 品牌，不得展示 Provider、model、Prompt、API Key、内部 Bot ID、调试日志或技术指标。

#### Scenario: Open an active link

- **WHEN** 访客扫描二维码或打开有效 Web Link
- **THEN** 页面展示对应 Bot 的 Ready 状态、公开介绍、Start voice call 和录音/文本保留提示，不自动请求麦克风

#### Scenario: Open an unavailable link

- **WHEN** 链接不存在、已停用或 Bot 不再可用
- **THEN** 页面展示 “This demo is no longer available.”，不创建 Session 且不泄露具体内部原因

### Requirement: Explicit microphone and connection flow

页面 MUST 只在访客点击 Start voice call 后请求麦克风权限；获得权限后才创建公开 Session 并开始 WebRTC 协商。连接成功前不得显示 Live、开始计时或播放 Opening Message。

#### Scenario: Grant microphone permission

- **WHEN** 访客点击 Start 并允许麦克风
- **THEN** 页面进入 Connecting，创建一次性 Session，WebRTC Connected 后进入 Live 并开始计时

#### Scenario: Deny microphone permission

- **WHEN** 访客拒绝权限或没有可用麦克风
- **THEN** 页面展示浏览器设置指导与 Retry，不创建可用通话、不开始录音

#### Scenario: Initial connection fails

- **WHEN** WebRTC 在有界尝试后仍未连接
- **THEN** 页面展示 “We couldn’t connect the call.” 与 Retry；Retry 必须创建新 Session，不复用旧 connection URL

### Requirement: Mobile live-call experience

Live 页面 MUST 用状态球与文字同时表达 Listening、Thinking、Speaking 和 Reconnecting；MUST 提供静音、字幕开关和挂断。主字幕卡 MUST 展示最近至少四句连续对话并对较早内容渐隐；完整 Transcript MUST 在只纵向滚动的抽屉中展示当前通话全部已确认文本。

#### Scenario: Receive the opening message

- **WHEN** WebRTC Connected 且 Bot 有非空 Opening Message
- **THEN** 系统播放并显示原始 Opening Message，不经 LLM 改写

#### Scenario: User interrupts the Agent

- **WHEN** Agent 播放期间检测到访客开口
- **THEN** 当前生成与播放按既有 barge-in 契约停止，页面立即切换为 Listening

#### Scenario: Toggle mute

- **WHEN** 访客开启 Mute
- **THEN** 客户端停止向 Pipeline 发送新的麦克风音频，取消 Mute 后恢复；静音不得提交空 Turn

#### Scenario: Toggle captions

- **WHEN** 访客关闭 Captions
- **THEN** 页面隐藏字幕卡，但 ASR、Transcript、历史和录音策略保持不变

#### Scenario: Open the Transcript drawer

- **WHEN** 访客点击不小于 36px 高的 `View transcript` 胶囊按钮或顶部 Transcript 图标
- **THEN** 抽屉展示当前通话全部已确认 Agent/You 消息，只允许纵向滚动且无横向溢出

### Requirement: Mobile call termination and recovery

页面 MUST 在访客挂断、达到最大时长、不可恢复断网或 Provider 失败时停止采集、生成和播放，并进入可理解的 Ended 或 Error 状态。再次通话 MUST 创建全新 Session。

#### Scenario: End a normal call

- **WHEN** 访客点击 End call
- **THEN** 页面停止媒体与 Pipeline，完成历史记录，展示时长和 Completed 状态

#### Scenario: Start another call

- **WHEN** 链接仍有效且访客点击 Call again
- **THEN** 页面创建新的单次 Session，不复用旧 token、PeerConnection 或 Pipeline 状态

#### Scenario: Recover a short network interruption

- **WHEN** 活跃通话发生短暂 ICE/网络中断
- **THEN** 页面进入 Reconnecting；恢复成功返回 Listening，失败则结束旧 Session 并提供 Retry

### Requirement: Mobile responsive and accessible layout

移动页面 MUST 在 320、375、390 和 430px 宽竖屏视口保持 `scrollWidth <= clientWidth`，所有主要触控热区不小于 44×44px，状态不得只依赖颜色表达；iOS Safari 与 Android Chrome 当前及前两个主要版本为首版支持目标。

#### Scenario: Use a narrow supported viewport

- **WHEN** 页面在 320px 宽和长文案状态下显示 Ready、Live、Transcript、Error 或 Ended
- **THEN** 主操作可见、内容正确换行，任何页面和抽屉都不产生横向滚动
