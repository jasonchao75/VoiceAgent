---
name: vendor-deepgram
description: 【内部依赖技能】包含 Deepgram ASR 专属的 API 参数、鉴权陷阱、MCP工具使用和核心规范。仅在执行 asr-survey 调研时主动加载本技能。
---

# Deepgram ASR 专属参考手册

> Agent 执行 Deepgram ASR 调研任务时，必须严格遵守本知识库提供的规约，不要随意去官网搜索过期资料。

## 1. 渐进式知识加载 (非常重要)
本技能采用了渐进式加载架构。根据用户的具体调研需求，你**必须**使用 `read` 工具阅读 `.opencode/skills/vendor-deepgram/deepgram-docs/` 目录下对应的官方文档备份，以获取准确的参数和终点(Endpoint)：
- 如果用户要求调研 **录音文件转写 (Pre-Recorded)**：读取 `deepgram-docs/pre-recorded.md` (使用 HTTP REST 接口)
- 如果用户要求调研 **Voice Agent 专用对话模型 (Flux v2)**：读取 `deepgram-docs/flux-v2-streaming.md` (使用 `/v2/listen` WebSocket 接口)
- 如果用户要求调研 **通用流式识别 (Streaming Nova)**：读取 `deepgram-docs/nova-v1-streaming.md` (使用 `/v1/listen` WebSocket 接口)

## 2. 鉴权与避坑 (极易踩坑)
- **WebSocket 鉴权**: Deepgram 的 WebSocket 鉴权通常需要在建立连接时，将 Token 以 `Authorization: Token YOUR_API_KEY` 的形式放在 Header 中。**注意：是 `Token` 前缀，不是 `Bearer`。**
- **HTTP 鉴权**: REST API 同样使用 `Authorization: Token YOUR_API_KEY`。
- **并发与保活（KeepAlive）**: 如果你的流式测试脚本长时间只收不发，Deepgram 会自动断开连接。请在脚本中实现发送心跳机制（KeepAlive消息），或者确保发送流和接收流双向协程同时稳定存活。
- **流式无自动语种检测**: Deepgram 的流式接口（WebSocket）**不支持**自动语种检测（`detect_language` 仅在录音文件 REST API 中可用）。必须通过 `language` 参数明确指定语种（如 `language=zh`），否则默认识别为英文，导致识别乱码。

## 3. Deepgram Agentic Tools 与 MCP Server (终极兜底方案)
Deepgram 官方提供了强大的 CLI 工具 (`dg`)，并内置了用于查询官方文档的 MCP Server。这比大模型去爬网页效果好得多。
- 如果本地 `deepgram-docs/` 里的文档不够用，或者你遇到了无法解决的特殊报错，可以向用户申请执行以下 Bash 命令安装其 CLI：
  `curl -fsSL https://deepgram.com/install.sh | sh`
- 安装完成后，你可以利用其提供的相关命令查询官方原生的资料体系。