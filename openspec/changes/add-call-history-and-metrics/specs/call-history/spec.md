# Delta: Call History

## Purpose

提供可控成本的通话录音、文本、诊断与延迟历史，为产品验收和未来 ASR Benchmark 数据筛选提供依据。

## ADDED Requirements

### Requirement: Persistent call history

系统必须持久化通话摘要、最终逐轮文本、安全错误诊断和延迟指标，并允许受 Basic Auth 保护的用户查看历史列表和详情。

#### Scenario: Review a completed call

- **WHEN** 用户在通话结束后打开历史详情
- **THEN** 页面按顺序展示最终用户 Transcript、助手文本、通话状态、错误和逐轮指标

### Requirement: User audio recording

系统必须默认保存进入 ASR 前的用户上行音频为无损、可用于后续 ASR Benchmark 筛选的格式，不保存 TTS 下行音频。

#### Scenario: Recording writer fails

- **WHEN** 录音队列溢出、编码失败或磁盘不可写
- **THEN** 系统停止该通话的录音并记录原因，但实时语音会话继续运行

### Requirement: Separate retention periods

文本、指标和元数据默认保留 30 天，录音默认保留 7 天。录音过期不得导致仍在保留期内的文本被删除。

#### Scenario: Recording reaches seven days

- **WHEN** 清理任务发现录音已超过配置的录音保留期
- **THEN** 删除录音文件并保留对应文本、指标和“录音已过期”状态

### Requirement: Recording capacity protection

系统必须限制录音总量，并在接近配额或最低剩余空间时按最旧优先删除录音。容量保护不得中断实时通话。

#### Scenario: Recording quota is exceeded

- **WHEN** 录音总量超过有效配额
- **THEN** 系统先删除最旧录音直至回到配额内，文本记录保持不变

### Requirement: History deletion

用户必须能够手动删除单条历史通话；删除后其文本、指标、诊断和录音必须一并移除。

#### Scenario: User confirms deletion

- **WHEN** 用户在二次确认后删除一条通话
- **THEN** 系统删除数据库关联记录与录音文件，并且该通话不再可查询

### Requirement: Recording disclosure

系统必须在用户开始通话前明确说明用户语音与对话文本会被保存及其默认保留期限。

#### Scenario: User prepares to start a call

- **WHEN** 页面显示可开始通话的操作
- **THEN** 同一区域可见录音 7 天、文本 30 天的保存提示

### Requirement: Benchmark-compatible metadata

录音记录必须关联音频格式、采样率、声道、语言、ASR provider/model、最终 Transcript、Bot ID 和稳定的 call/turn 标识，但不得自动进入长期 Benchmark 数据集。

#### Scenario: Recording is later selected for evaluation

- **WHEN** 后续独立流程人工选择一段历史录音
- **THEN** 所需音频契约和识别上下文可以从历史记录中完整获取
