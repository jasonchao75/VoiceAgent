# add-english-flux-voice-agent

## Why（为什么要做）

当前项目已经完成 Pipecat 技术选型和部分 ASR 厂商验证，但尚无可运行的实时 Voice Agent。
第一版需要先形成一条可以本地验收、随后部署为受保护公网 Demo 的最小闭环，用于验证 Deepgram Flux ASR、Flux TTS、流式 LLM、打断和浏览器交互是否能够稳定协同。

## What（这次要做什么）

- 使用 Pipecat 搭建全异步实时 Pipeline：浏览器音频 → Deepgram Flux ASR → 流式 LLM → Deepgram Flux TTS → 浏览器播放。
- 第一版只实现 Deepgram Flux TTS，同时建立清晰的 TTS Provider 扩展接口，为后续 ElevenLabs 适配器预留接入点。
- 提供参考 Vapi 信息架构的英文 Voice Agent 测试页面，但不复制其品牌与视觉资产。
- 前端支持配置 System Prompt、Opening Script、LLM 模型、Flux Voice，以及用户自己的 Deepgram/LLM API Key；配置在新会话开始时生效。
- 前端为 Flux Voice 提供带人物特征的下拉选项，为 LLM 提供 Provider 预设、推荐 model 与高级自定义输入，并在对应字段旁提供官方 API Key/模型文档入口，避免要求用户自行猜测 ID。
- Deepgram 和 LLM 全部采用 BYOK，不提供任何共享默认厂商 Key。Key 仅用于创建当前会话，后端只在内存中保存并在会话结束或超时后清除。
- 支持 Agent 主动播放 Opening Script、多轮英语对话、实时 transcript、通话状态和用户打断。
- 提供不要求手工安装 Python 的一键本地启动方式，并完成最小自动化测试与人工验收清单。
- 本地验收通过后，经用户单独确认，再部署到 DigitalOcean 公网 Demo。

## Delivery Strategy（交付策略）

1. **本地阶段**：由开发环境完成依赖安装、自动化检查和浏览器人工验收；用户只需要访问本地 URL，不需要手工搭建 Python 环境。
2. **公网阶段**：复用同一构建产物部署到 DigitalOcean，使用 HTTPS/WSS、访问保护和会话级 BYOK；服务器不保存共享 Deepgram/LLM Key。
3. **持续交付阶段**：push/PR 自动执行完整 CI；`main` 的 CI 全绿后自动部署 `platform.voiceagentdemo.org`，部署失败不得替换健康版本，并保留手动重跑入口。
4. DigitalOcean 资源创建、域名/DNS、付费资源使用、服务器凭证配置和真实厂商 API 连通性测试，均需在执行前取得用户确认。

## Out of Scope（这次明确不做什么）

- 不实现 ElevenLabs TTS，只保留 Provider 扩展接口。
- 不接 FreeSWITCH、SIP 或电话线路。
- 不做多租户、用户注册、数据库配置中心或完整管理后台。
- 不做 Function Calling、MCP、知识库、长期记忆和复杂业务流程。
- 不做多语种；第一版只支持英语。
- 不承诺生产级高可用、自动扩缩容和正式 SLA。
- 不以 Vapi 作为运行时编排层，也不复制 Vapi 的代码、品牌或受版权保护素材。

## Success Criteria（成功标准）

- 用户可在浏览器打开页面、授权麦克风并开始/结束会话。
- Opening Script 能在会话开始后通过 Flux TTS 播放，并进入 LLM 对话上下文。
- 用户英语语音能够被 Flux ASR 转写，LLM 能流式回复，Flux TTS 能流式播放。
- 用户在 Agent 播放期间说话时，浏览器能及时停止旧音频，Pipeline 能取消旧轮次并处理新输入。
- System Prompt、Opening Script、LLM 模型和 Flux Voice 的会话级配置能够生效。
- 用户无需离开配置上下文即可了解如何获取 Deepgram/LLM API Key、Flux Voice ID 和 LLM model ID；推荐项过期时仍可通过官方文档与高级自定义完成配置。
- 页面显示实时 transcript、连接状态、当前发言方以及基础延迟指标。
- Deepgram 与 LLM API Key 只出现在遮罩输入框和初始 HTTPS 会话创建请求体中；不得进入 URL、Local Storage、WebSocket 消息、服务端日志、接口响应或仓库，并在会话结束或超时后从后端内存清除。
- 本地启动、自动化检查、异常处理和 DigitalOcean 部署路径均有可执行说明。
- 合入 `main` 后自动执行 CI；仅 CI 全绿的 `main` 提交可自动部署到公网 Demo，并完成健康检查与失败回滚。

## Relevant References（相关参考）

- `AGENTS.md`
- `.opencode/skills/pipecat-integration/SKILL.md`
- `docs/engineering/deployment-digitalocean-demo.md`
- Deepgram Flux ASR `/v2/listen` 官方文档
- Deepgram Flux TTS `/v2/speak` 官方文档
- Pipecat `DeepgramFluxSTTService` / `DeepgramFluxTTSService` 官方实现与示例
