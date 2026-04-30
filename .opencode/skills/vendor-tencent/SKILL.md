---
name: vendor-tencent
description: 【内部依赖技能】包含腾讯云 ASR (实时语音识别) 专属的 API 参数、极其复杂的签名鉴权陷阱和核心规范。仅在执行 asr-survey 调研时主动加载本技能。
---

# 腾讯云 ASR (Tencent Cloud) 专属参考手册

> Agent 执行腾讯云 ASR 调研任务时，必须严格遵守本知识库提供的规约。由于腾讯云的鉴权机制远比海外厂商复杂，**强烈建议使用腾讯云官方 SDK** (例如 `tencentcloud-speech-sdk-python`) 进行流式接入，或者在必要时查阅官方参考文档手动实现签名。

## 1. 渐进式知识加载 (非常重要)
本技能采用了渐进式加载架构。根据用户的具体调研需求，你**必须**使用 `read` 工具阅读 `.opencode/skills/vendor-tencent/tencent-docs/` 目录下对应的官方文档备份，以获取准确的参数和终点(Endpoint)：
- 针对语音助手/电话机器人的场景，目前仅提供流式识别：读取 `tencent-docs/realtime-streaming.md` (极度强烈建议使用 `tencentcloud-speech-sdk-python`)。

## 2. 鉴权与避坑 (极易踩坑)
- **复杂的签名验证 (HMAC-SHA1)**: 腾讯云的底层 REST/WebSocket 接口不使用简单的 Header 或单一的 API Key 参数。每一次 WebSocket 的 URL 都必须计算并携带 `signature` 参数，它是基于 AppID, SecretId, Timestamp, Expired 和各类参数严格按字典序排序后计算出的结果。
- **强制使用 SDK**: 由于底层签名机制的复杂性以及连接管理难度，**绝对不要尝试手写 WebSocket 连接**。必须使用官方的 SDK `tencentcloud-speech-sdk-python`。
- **并发控制**: 默认单账号限制并发数为200路。如果需要做压力测试，需提前留意。

## 3. 业务强制红线
- **绝不硬编码密钥**: `TENCENTCLOUD_SECRET_ID`、`TENCENTCLOUD_SECRET_KEY` 以及 `TENCENTCLOUD_APPID` 必须从 `.env` 环境变量中读取。
- **防幻觉红线**: 提取大模型引擎类型（如 `16k_zh_large`, `8k_zh_large`）和热词（`hotword_id` / `hotword_list`）时，绝对要以上方备份的 API 原文规范为准，切勿自造不存在的配置。

