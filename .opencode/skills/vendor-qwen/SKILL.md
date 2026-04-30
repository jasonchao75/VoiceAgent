---
name: vendor-qwen
description: 【内部依赖技能】包含阿里云大模型（DashScope）千问 Qwen-ASR-Realtime 专属的 SDK 参数、鉴权陷阱和核心规范。仅在执行 asr-survey 调研时主动加载本技能。
---

# 阿里云 Qwen-ASR 专属参考手册

> Agent 执行 Qwen-ASR 调研任务时，必须严格遵守本知识库提供的规约。Qwen-ASR（百炼平台）在流式语音识别方面提供了基于 WebSocket 的双向流式接口，官方强烈推荐使用 DashScope Python SDK 进行对接。

## 1. 渐进式知识加载 (非常重要)
本技能采用了渐进式加载架构。根据用户的具体调研需求，你**必须**使用 `read` 工具阅读 `.opencode/skills/vendor-qwen/qwen-docs/` 目录下对应的官方文档备份，以获取准确的参数和终点(Endpoint)：
- 如果用户要求调研 **实时流式双向语音识别**：读取 `qwen-docs/realtime-streaming.md` (使用 `OmniRealtimeConversation` 接口)。
- 如果用户要求调研 **离线长音频转写 (Async Batch)**：读取 `qwen-docs/batch-prerecorded.md` (使用 DashScope 异步任务接口)。

## 2. 鉴权与避坑 (极易踩坑)
- **SDK 鉴权**: 在 Python SDK 中，通常设置环境变量 `DASHSCOPE_API_KEY`，SDK 内部会自动获取。
- **真正的双向流式**: 与之前的短语音/文件转写 API 不同，阿里云为实时对话场景专门提供了 `OmniRealtimeConversation` 类，它基于 WebSocket (`wss://dashscope.aliyuncs.com/api-ws/v1/realtime`)，支持边发音频边接收识别结果，同时支持服务端 VAD (Voice Activity Detection)。
- **地域端点差异**: 阿里云模型分为中国内地（北京）和国际（新加坡/美国），各自的 URL 和 API Key 是隔离的。默认中国内地的 URL 为 `wss://dashscope.aliyuncs.com/api-ws/v1/realtime`。

## 3. 业务强制红线
- **绝不硬编码密钥**: `DASHSCOPE_API_KEY` 必须从 `.env` 环境变量中读取。
- **防幻觉红线**: 编写 `OmniRealtimeConversation` 代码时，务必参考官方 API 定义，确保使用正确的 VAD 配置和 `MultiModality` 参数，绝不凭空臆造。
