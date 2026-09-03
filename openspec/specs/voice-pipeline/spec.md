# Voice Pipeline Specification

## Purpose

定义浏览器实时语音会话中 ASR、LLM、TTS 的核心编排行为。

## Requirements

### Requirement: Asynchronous streaming pipeline

系统必须通过异步流式 Pipeline 依次处理浏览器音频输入、Deepgram Flux STT、对话上下文、OpenAI-compatible LLM、TTS 和浏览器音频输出，核心热路径不得使用同步阻塞 I/O。

#### Scenario: Browser starts a conversation

- **WHEN** 客户端使用有效令牌建立 WebSocket 并发送音频
- **THEN** 音频和生成结果以流式方式经过 Pipeline，不要求整段音频落盘后再处理

### Requirement: Fixed opening script

配置了 Opening Script 时，系统必须在客户端准备完成后直接交给 TTS 播放，并把相同内容加入助手对话上下文，不得先让 LLM 改写。

#### Scenario: Client becomes ready

- **WHEN** 会话配置包含非空 Opening Script 且客户端发送 ready 事件
- **THEN** 系统播放原始 Opening Script

### Requirement: Session termination

客户端断开、空闲超时或达到最大会话时长时，系统必须取消正在进行的生成和播放工作并释放会话资源。

#### Scenario: Browser disconnects during generation

- **WHEN** 浏览器在 LLM 或 TTS 仍在工作时断开
- **THEN** 系统取消对应 Pipeline Worker
