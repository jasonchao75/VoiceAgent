## ADDED Requirements

### Requirement: Deepgram Flux voice settings

系统 MUST 在创建 Deepgram Flux streaming TTS 连接时传入当前 Bot 的 `speed` 与 `expressivity`，且不得改变现有音频格式、文本聚合、打断和时延统计契约。

#### Scenario: Start Flux with voice controls

- **WHEN** Bot 配置 `speed=1.05`、`expressivity=1` 并启动会话
- **THEN** Flux WebSocket 使用所选 voice、Speed 和 Expressivity 建立连接，其他 Pipeline 行为保持不变

