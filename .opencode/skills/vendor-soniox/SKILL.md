---
name: vendor-soniox
description: 【内部依赖技能】包含 Soniox ASR 专属的 API 参数、鉴权陷阱、MCP工具使用和核心规范。仅在执行 asr-survey 调研时主动加载本技能。
---

# Soniox ASR 专属参考手册

> Agent 执行 Soniox ASR 调研任务时，必须严格遵守本知识库提供的规约，不要随意去官网搜索过期资料。

## 1. 渐进式知识加载 (非常重要)
本技能采用了渐进式加载架构。根据用户的具体调研需求，你**必须**使用 `read` 工具阅读 `.opencode/skills/vendor-soniox/soniox-docs/` 目录下对应的官方文档备份，以获取准确的参数和终点(Endpoint)：
- 如果用户要求调研 **通用流式识别与翻译 (Realtime Streaming)**：读取 `soniox-docs/realtime-streaming.md` (使用 WebSocket 接口 `wss://stt-rt.soniox.com/transcribe-websocket`)
- 如果用户要求调研 **离线批量转写 (Async Batch)**：读取 `soniox-docs/batch-prerecorded.md` (使用 HTTP REST 接口 `/v1/transcriptions`)

## 2. 鉴权与避坑 (极易踩坑)
- **WebSocket 鉴权 (非常特殊)**: Soniox 的 WebSocket **不使用** Header 鉴权或 Query 鉴权，而是在建立连接后，发送的第一条消息**必须是包含 `api_key` 字段的 JSON 字符串**。
- **HTTP 鉴权**: REST API 使用标准的 `Authorization: Bearer YOUR_API_KEY`。
- **音频格式配置必填**: VoiceAgent 电话/实时场景中，**严禁使用 `"auto"`**，必须显式指定 `raw audio` 参数（`audio_format="pcm_s16le"`, `sample_rate=16000` 或 `8000`, `num_channels=1`）。
- **Token 演化机制**: 流式响应下发 Token 列表，分为 `is_final: false`（临时猜测，会被覆盖）和 `is_final: true`（确定结果，只下发一次）。客户端必须自己累加维护 Final Tokens。
- **音频流结束**: 客户端必须发送**空字符串 `""` (Text Frame)** 以通知服务端结束音频流，否则会一直等待。

## 3. Soniox MCP Server (官方推荐)
Soniox 官方提供了基于 MCP (Model Context Protocol) 的文档服务器，可以直接在开发环境中浏览 API 文档和示例。
如果本地文档无法满足需求，可以通过以下方式使用其 MCP Server：
```bash
npx -y mcp-remote https://soniox.com/docs/api/mcp/mcp
```
这能让 AI 助手直接访问最新的 Soniox 官方文档和参考代码，极大减少开发过程中的幻觉。

## 4. 业务强制红线
- **绝不硬编码密钥**: `SONIOX_API_KEY` 必须从 `.env` 环境变量中读取。
- **禁止捏造参数**: 必须严格遵循 `stt-rt-v4` 等模型在参考文档中的参数白名单。
