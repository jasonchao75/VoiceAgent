# Call History Delta Specification

## ADDED Requirements

### Requirement: Mobile Web Call history classification

系统 MUST 将公开移动 WebRTC 通话保存到现有历史、用户上行录音和逐轮指标体系，并使用 `mobile_web_call` 作为独立来源。该来源 MUST 遵循录音 7 天、文本/指标 30 天的现有保留与容量清理契约。

#### Scenario: Complete a mobile demo call

- **WHEN** `mobile_web_call` 正常结束
- **THEN** Sessions 列表和详情展示绑定 Bot、最终 Transcript、用户录音、逐轮指标、时长和完成状态，并可按移动来源区分

#### Scenario: Fail during WebRTC negotiation

- **WHEN** Session 已创建但 WebRTC 未成功进入媒体连接
- **THEN** 历史不得伪造对话 Turn 或录音；若保留尝试记录，必须显示准确的连接失败状态和安全错误分类

#### Scenario: Disclose retention before recording

- **WHEN** 访客尚未点击 Start voice call
- **THEN** 移动 Ready 页在主按钮同一区域明确展示用户语音保留 7 天、Transcript 与指标保留 30 天
