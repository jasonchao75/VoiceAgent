## ADDED Requirements

### Requirement: Test pages expose the active voice pipeline

系统 MUST 提供独立 Chat test 与 Web call test 二级页面。两者 MUST 使用 Start/End 生命周期、播放 Opening message、显示对话内容，并在每条 Agent 回复下方就近展示该 Turn 的真实指标。

#### Scenario: Run a Chat test

- **WHEN** 用户开始 Chat test、发送文本并收到 Agent 回复
- **THEN** 系统绕过 ASR 但执行 LLM + TTS，在回复下展示 LLM splicing、LLM TTFT、TTS initial、TTS TTFT、playback 与 E2E；不得展示 ASR final 数值

#### Scenario: Interrupt Chat test playback

- **WHEN** Agent TTS 尚在播放且用户再次发送文本
- **THEN** 当前 playback 被打断，该事件记录为 barge-in，新文本开始下一交互轮次

#### Scenario: Run a Web call test

- **WHEN** 用户开始 Web call 并完成一个 Caller→Agent Turn
- **THEN** 页面显示双方实时字幕，并在 Agent 回复下展示 Chat 指标集合加 ASR final

#### Scenario: Keep simulation out of production

- **WHEN** 正式 Web call 页面实现用户输入
- **THEN** 用户通过麦克风说话，原型的 `Simulate caller turn` 控件不存在

### Requirement: Sessions list and detail drawer

Sessions MUST 以时间倒序逐条列表展示历史记录，并支持时间和类型筛选。每条记录 MUST 提供 View；点击后 MUST 在可收起的非模态右侧抽屉展示详情，且列表仍留在主工作区。

#### Scenario: Open a Session detail

- **WHEN** 用户点击某条记录的 View
- **THEN** 右侧抽屉显示该记录概要、历史录音、字幕和逐 Turn 指标；关闭抽屉后恢复列表宽度

#### Scenario: Review a transcript

- **WHEN** 用户查看历史字幕
- **THEN** 双方通过气泡位置和颜色区分，不重复展示 Agent/Caller 标签；每个指标卡紧邻所属 Agent 回复

#### Scenario: Play retained user audio

- **WHEN** Web call Session 的用户上行录音仍在保留期内
- **THEN** 抽屉在字幕上方提供播放器及格式、声道、采样率和剩余保留期信息，并明确不包含 Agent TTS

#### Scenario: Open a Chat test Session

- **WHEN** Session 类型为 Chat test
- **THEN** 详情说明该测试使用文本输入、没有用户录音，并使用不含 ASR final 的 Turn 指标结构

#### Scenario: Recording is unavailable

- **WHEN** 录音过期、写入失败或已被容量清理
- **THEN** 详情保留字幕和指标，并在播放器位置显示明确的不可用原因
