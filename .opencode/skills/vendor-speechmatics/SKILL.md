---
name: vendor-speechmatics
description: 【内部依赖技能】包含 Speechmatics ASR 专属的 API 参数、鉴权陷阱和核心规范。仅在执行 asr-survey 调研时主动加载本技能。
---

# Speechmatics ASR 专属参考手册

> Agent 执行 Speechmatics ASR 调研任务时，必须严格遵守本知识库提供的规约，不要随意去官网搜索过期资料。

## 1. 渐进式知识加载 (非常重要)
本技能采用了渐进式加载架构。根据用户的具体调研需求，你**必须**使用 `read` 工具阅读 `.opencode/skills/vendor-speechmatics/speechmatics-docs/` 目录下对应的官方文档备份，以获取准确的参数和终点(Endpoint)：
- 如果用户要求调研 **通用流式识别 (Realtime Streaming)**：读取 `speechmatics-docs/realtime-streaming.md` (使用 `wss://eu.rt.speechmatics.com/v2/` WebSocket 接口)
- 如果用户要求调研 **语音助手专属流式接口 (Voice Agent API Preview)**：读取 `speechmatics-docs/voice-agent-api.md` (使用 `wss://preview.rt.speechmatics.com/v2/agent/<profile>`，内置 Turn-Detection 和 VAD，非常适合语音机器人项目)
- 如果用户要求调研 **录音文件转写 (Batch Pre-Recorded)**：读取 `speechmatics-docs/batch-prerecorded.md` (使用 HTTP REST 接口)

## 2. 鉴权与避坑 (极易踩坑)
- **官方 SDK 与 API 示例参考**: Speechmatics 提供了官方 Python SDK (`speechmatics-python-sdk`)。在他们的 Github 仓库 `examples/` 目录下，不仅有 SDK 的使用示例，也**包含了原生 API 的调用示例（如直接通过 websockets 库构造请求）**。如果遇到 JSON 字段拼装或并发处理的问题，请务必参考官方的原生 API 示例。
- **WebSocket 鉴权 (可靠性已验证)**: Speechmatics 的 WebSocket 鉴权在 HTTP Handshake 阶段通过 Header 传递：`Authorization: Bearer YOUR_API_KEY`。**注意：前缀是 `Bearer`，不要与 Deepgram 的 Token 混淆。** 如果在浏览器环境无法修改 Header，可以使用 URL 参数 `?jwt=<temporary-key>`；在 Voice Agent API 中还可以使用 `?api_key=<YOUR_API_KEY>`。
- **HTTP 鉴权**: REST API 同样使用 `Authorization: Bearer YOUR_API_KEY`。
- **并发与保活（KeepAlive）**: Speechmatics 会实施超时断开策略（idle_timeout），如果在 1 小时内没有发送任何音频数据（或在 48 小时后强制断开），连接会关闭。流式识别在完成一段话后，如果不结束会话，建议持续发送环境静音数据或进行重连管理。
- **音频格式配置必填**: 在建立 WebSocket 连接后，第一条发送的消息必须是 `StartRecognition`，必须包含明确的 `audio_format` (如 `{ "type": "raw", "encoding": "pcm_s16le", "sample_rate": 8000 }`) 和 `transcription_config`。Voice Agent API 端点仅支持 `8000` 或 `16000`。
- **语言强制指定**: `transcription_config` 中的 `language` 参数是必填的（例如 `language="zh"`）。
- **发送音频的时机**: 必须在接收到服务器回复的 `RecognitionStarted` 消息之后，才能开始发送二进制格式的音频片段 (`AddAudio`)。在收到 `EndOfStream` 回应前持续发送。

## 3. 业务强制红线
- **电话流式场景强制要求音频格式为 8KHz / 16bit / 单声道 PCM**。因此向 Speechmatics 发送的 `StartRecognition` 握手中必须携带 `{"audio_format": {"type": "raw", "encoding": "pcm_s16le", "sample_rate": 8000}}`。
- **绝不硬编码密钥**: `SPEECHMATICS_API_KEY` 必须从 `.env` 中读取。
