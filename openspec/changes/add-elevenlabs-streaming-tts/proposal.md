# Proposal: Add ElevenLabs Streaming TTS

## Why

Platform 目前只能使用 Deepgram Flux TTS，无法在同一 Bot 中比较不同 TTS 厂商的音质、首包延迟和打断表现。ElevenLabs 提供适合 LLM token 流输入的 WebSocket `stream-input` 接口，可在一个长连接中持续发送文本并接收音频。

## What Changes

- TTS provider 增加 `elevenlabs`，Deepgram Flux 保持默认且向后兼容。
- ElevenLabs 使用 Pipecat 原生 `ElevenLabsTTSService`，底层连接官方 `/v1/text-to-speech/{voice_id}/stream-input` WebSocket。
- Bot 配置增加两家 TTS 共用的 Token/Sentence text aggregation，以及 ElevenLabs model 与可调 voice settings；ElevenLabs 默认 `eleven_flash_v2_5`，支持 Turbo v2.5、Multilingual v2 与 Eleven v3，输出保持 24 kHz、16-bit、单声道 PCM。
- Bot/Session 增加独立 ElevenLabs API Key，按 provider 条件校验；选择 Deepgram 时不要求 ElevenLabs Key。
- ElevenLabs voice 使用账号级动态 voice 列表，并允许手工填写 voice ID 作为降级方案。
- 保存 Key 时新增独立 Fernet 加密列；API、日志和历史记录不得返回或记录明文/密文。
- 保持 LLM text streaming、音频 chunk → 浏览器播放、barge-in 取消和 provider-neutral latency capture；历史同时记录 text aggregation，避免跨模式误比延迟。

## Out of Scope

- ElevenLabs Conversational AI/Agents Platform。
- `eleven_v3` Text-to-Dialogue 多说话人编排；本 Change 只使用现有单音色 TTS WebSocket。
- Voice caching、pronunciation dictionaries、fallback voices 和由 LLM 直接产生 SSML/audio tags。
- 自动克隆、创建、删除 ElevenLabs voices。
- 自动执行会产生 TTS credits 的真实合成；由用户确认后单独验收。

## Success Criteria

- Bot 可在 Deepgram Flux 与 ElevenLabs 之间切换并保存。
- 两家 TTS 都可选 Token/Sentence；新 Bot 默认 Token，ElevenLabs Auto mode 根据该选择自动联动。
- ElevenLabs 可配置四种模型和原型确认的 voice settings，v3 不传递其不支持的参数。
- ElevenLabs Key 仅在选择 ElevenLabs 时必填，且可选择加密保存或仅会话使用。
- LLM 流式文本通过单个 ElevenLabs WebSocket 生成连续 PCM 音频并实时播放。
- 打断时停止当前 ElevenLabs 合成与浏览器播放，不污染下一轮。
- mock 测试覆盖 provider 构建、条件凭证、迁移、voice 查询失败降级和 pipeline 选择。
