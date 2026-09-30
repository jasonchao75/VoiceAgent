# Change: Add Mobile WebRTC Demo Sharing

## Why

VoiceAgent 当前只有受后台登录保护的桌面 Web Call 测试页，无法让演示访客通过手机扫码直接体验指定 Bot。真实 SIP 线路在中国大陆存在企业资质和线路成本门槛，本阶段需要一个不依赖电话号码、无需访客登录且更适合移动网络的演示入口。

## What Changes

- 为 Bot 增加草稿/不可变发布快照、独立公开 title/description 与受后台登录保护的 `Share` 页面。
- 每个 Published Bot 提供一个稳定的公开 Demo Link，并以 Web Link 与二维码两种方式分享。
- 支持复制链接、下载二维码、打开预览、停用和重新启用；停用不更换公开标识。
- 新增无需后台登录的移动通话页，覆盖 Ready、权限、连接、实时通话、弱网、失败和结束状态。
- 新增 Pipecat Small WebRTC 传输路径；保留现有 WebSocket Chat/Web Call 测试路径并复用同一 ASR → LLM → TTS Pipeline。
- 移动会话以 `mobile_web_call` 写入现有历史、录音和逐轮指标体系。

## PRD and Prototype First

- PRD: `docs/prd/mobile-webrtc-demo/VoiceAgent_Mobile_Web_Call_PRD_V0.1.0.md`（文档内版本 V0.1.2）
- Mobile prototype: `prototypes/mobile-call.html`
- Admin Share prototype: `prototypes/admin-share.html`
- User Gate 1 前禁止编写正式页面、Demo Link 持久化、WebRTC 信令或 Pipeline 核心逻辑。
- Q-001/Q-002 已确认；更新后的原型需要记录唯一 SHA-256 baseline 后才可进入实现。

## In Scope

- 单 Bot 发布、一个稳定 Demo Link、二维码与 Web Link。
- 公开移动页主动发起 WebRTC 音频通话。
- 麦克风权限、连接/重连/失败、Listening/Thinking/Speaking、实时字幕、完整 Transcript、静音、挂断、再次通话。
- Opening Message、barge-in、通话内语速控制、录音、历史和逐轮指标复用。
- 当前最多 3 路并发与现有 7/30 天保留策略。
- iOS Safari 与 Android Chrome 当前及前两个主要版本。

## Out of Scope

- SIP、FreeSWITCH、电话号码、真实呼入/外呼。
- 原生 App、PWA 安装引导、后台来电、推送和锁屏接听。
- TURN 中继、多人房间、视频、屏幕共享和转人工。
- 多链接、到期时间、访问密码、短 PIN、链接重新生成和批量分享。
- 移动端 Provider、密钥、技术指标、费用或调试信息。
- 任何真实客户数据或付费外部测试调用。

## Impact

- Affected specs: `bot-config`, `voice-session`, `call-history`; new capability: `mobile-web-call`。
- Affected future code: Bot/demo-link storage, auth public-route policy, session admission, WebRTC request handler/transport factory, mobile frontend, admin Share UI, history filters and tests。
- New runtime dependencies proposed: Python `pipecat-ai[webrtc]`/`aiortc`, frontend `@pipecat-ai/small-webrtc-transport`, and one local QR encoder selected and pinned before implementation。
- UI risk: High；必须执行两个用户 Gate 与三个研发检查点。
