---
name: vendor-azure
description: 【内部依赖技能】包含 Azure Cognitive Services Speech (微软云 ASR) 专属的 SDK 与 API 参数、鉴权陷阱和核心规范。仅在执行 asr-survey 调研时主动加载本技能。
---

# Azure Speech ASR 专属参考手册

> Agent 执行 Azure ASR 调研任务时，必须严格遵守本知识库提供的规约。Azure 的认证体系和调用方式（以官方 SDK 为主）与其他纯 WebSocket 厂商存在较大区别。

## 1. 渐进式知识加载 (非常重要)
本技能采用了渐进式加载架构。根据用户的具体调研需求，你**必须**使用 `read` 工具阅读 `.opencode/skills/vendor-azure/azure-docs/` 目录下对应的官方文档备份，以获取准确的参数：
- 如果用户要求调研 **实时流式识别 (Realtime Streaming)**：读取 `azure-docs/realtime-streaming.md` (强烈建议使用官方 Speech SDK，而非手写 WebSocket)。
- 如果用户要求调研 **离线批量转写或短音频识别 (Batch / Fast Transcription)**：读取 `azure-docs/batch-prerecorded.md` (使用 HTTP REST 接口)。

## 2. 鉴权与避坑 (极易踩坑)
- **非纯 Token 鉴权**: Azure 的很多服务不支持直接用一个全局 Token 搞定。你需要两个核心环境变量：
  1. `AZURE_SPEECH_KEY` (Ocp-Apim-Subscription-Key)
  2. `AZURE_SPEECH_REGION` (如 `eastus`, `westus`)
- **WebSocket 官方建议**: Azure 官方强烈建议使用各个语言的 `azure-cognitiveservices-speech` SDK 来完成流式识别（内部封装了复杂的 Token 获取与 WebSocket 重连机制）。如果非要手写 WebSocket，难度极大，优先使用 SDK。
- **音频格式**: Azure SDK 支持从文件读取流或直接 Push Stream。处理流式音频时，必须正确设置 `AudioStreamFormat.get_wave_format_pcm(16000, 16, 1)` 等属性。

## 3. 业务强制红线
- **绝不硬编码密钥**: `AZURE_SPEECH_KEY` 和 `AZURE_SPEECH_REGION` 必须从 `.env` 环境变量中读取。
- **防幻觉红线**: Azure 的接口版本非常多（v3.0 已废弃，当前 REST API 主要是 `2024-11-15` 或 `2025-10-15` 等基于 API Version 的端点）。绝不允许凭记忆捏造老旧的 URL。
