---
name: vendor-elevenlabs
description: 【内部依赖技能】包含 ElevenLabs Scribe 实时语音识别 (Realtime STT) 专属的 API 参数、鉴权陷阱和核心规范。仅在执行 asr-survey 调研时主动加载本技能。
---

# ElevenLabs Realtime STT 专属参考手册

> Agent 执行 ElevenLabs ASR 调研或对接开发任务时，必须严格遵守本知识库提供的规约，不要使用臆想参数或混淆其它 ASR 厂商接口。

## 1. 渐进式知识加载 (非常重要)
本技能采用了解耦设计。在后续深度对接或编写适配器时，你**必须**使用 `read` 工具阅读 `.opencode/skills/vendor-elevenlabs/elevenlabs-docs/` 目录下对应的官方文档备份，以获取最精确的参数类型和错误定义：
- 如果进行 **通用实时流式识别 (Realtime Streaming STT)**：读取 `elevenlabs-docs/realtime-streaming.md` (包含 2026 最新官方 AsyncAPI 2.6.0 规格，避免大模型生成幻觉参数)

## 2. 鉴权与避坑指南 (极易踩坑 ⚠️)

- **WebSocket 与 REST 架构分工**:
  - 实时 STT 是通过 **WebSocket 双向流** 运行的。
  - 握手配置**全部放置在 URL 的 Query Parameters 中**（例如 `?model_id=scribe_v2_realtime&audio_format=pcm_8000&commit_strategy=vad`），建立连接后无法动态修改，这与 Speechmatics (通过 JSON 消息 `StartRecognition` 动态配置) 具有本质区别。
- **数据帧格式差异 (核心痛点)**:
  - 绝大多数 ASR 厂商（如 Speechmatics、Deepgram、Soniox）在 WebSocket 建立后直接推入 **Raw Binary PCM** 字节流。
  - **ElevenLabs 绝对不允许直接推送二进制字节！** 客户端的音频输入必须以 JSON 字符串形式发送，音频必须采用 **Base64 编码**：
    ```json
    {
      "message_type": "input_audio_chunk",
      "audio_base_64": "UklGRiS9A...",
      "commit": false,
      "sample_rate": 8000
    }
    ```
    向 ElevenLabs 直接推送二进制数据会导致连接被立即切断。
- **WebSocket 握手鉴权**:
  - 在服务端对接时，通常在 HTTP 握手阶段在 Header 中携带 `xi-api-key: YOUR_API_KEY` 进行认证。
  - 在客户端/浏览器沙盒环境，不能定制 Header，推荐先调用 `POST /v1/tokens` 接口获取单次有效临时 Token，再拼接在连接 URL 中：`?token=<SINGLE_USE_TOKEN>`。
- **双向并发与握手依赖**:
  - 握手成功后，ElevenLabs 会立即向客户端推送 `session_started` 消息。
  - **红线要求**: 客户端必须在接收到 `session_started` 事件并校验 `session_id` 后，才能开始 streaming 发送音频 JSON 块。

## 3. 业务强制红线 (Mandatory Constraints)

- **电话流式场景音频对齐**:
  - 本项目电话网关音频格式为 **8KHz / 16bit / 单声道 PCM**。因此，传入 ElevenLabs WebSocket 的 URL 参数中必须显式设置 `audio_format=pcm_8000`，并且在每一个 `input_audio_chunk` 中的 `sample_rate` 设为 `8000`。
- **外部化配置约束**:
  - 适配器代码中绝对不允许硬编码模型名、VAD 阈值、静音时长、提交策略等参数。必须毫无遗漏地全部外置于 `configs/vendor/elevenlabs/config.json` 中并支持热加载。
- **密钥零泄露**:
  - `ELEVENLABS_API_KEY` 必须从 `.env` 环境变量读取，绝不能出现任何硬编码密钥或在验证脚本中输出明文密钥。
