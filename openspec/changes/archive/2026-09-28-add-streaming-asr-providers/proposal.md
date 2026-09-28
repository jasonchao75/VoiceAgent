# Change: Add Streaming ASR Providers

## Why

VoiceAgent 当前实时 Pipeline、Bot 配置、凭证和 UI 只支持 Deepgram Flux。产品需要为 Deepgram 增加 Nova-3，并新增 Speechmatics Realtime Enhanced、Soniox `stt-rt-v5` 与 AssemblyAI `universal-3-5-pro`；同时让 AssemblyAI 使用 Agent Context 与用户历史 Carryover 改善多轮识别。

## What Changes

- 新增 ASR Service 抽象与 Provider Registry，Deepgram Flux/Nova-3 与三家新供应商通过统一创建边界进入 Pipeline。
- Bot ASR 配置改为公共字段加 Provider 专属严格配置；Catalog 提供四家模型和语言能力。
- ASR、TTS、LLM 凭证按 Bot、组件与 Provider 分开加密保存，支持组件混搭且不同 Bot 可使用不同账号；全局资源管理延后。
- 四家转写、Turn、打断、错误和时延归一化为公共 Frame/事件。
- Turn Detection Source 本期只提供 Provider-native 与 Off；Off 定义为关闭智能 Turn Detection、保留 VAD/固定静音切分，Catalog 按 Provider/model 声明能力，Self-developed 留待未来 Change。
- AssemblyAI 同一会话保留 Final 用户历史；完整 Assistant Turn 并行发送给 TTS 和 ASR Context 更新。
- ASR 抽屉增加 Provider 选择和专属参数；保持当前产品布局和 16 kHz PCM 输入。

## PRD and Prototype First

- PRD: `docs/prd/VoiceAgent_Streaming_ASR_MultiProvider_PRD_V1.0.0.md`
- Prototype: `prototypes/index.html`
- User Gate 1 前禁止编写正式页面、Adapter、迁移或凭证代码。
- User Gate 1 已由 D-014 确认；当前原型已冻结唯一 SHA-256 baseline，任何有意偏离必须先更新 Change 并重新确认。

## In Scope

- Deepgram Flux 兼容基线与 Deepgram Nova-3 V1 Streaming。
- Speechmatics Realtime Enhanced、Soniox stt-rt-v5、AssemblyAI Universal-3.5 Pro Realtime。
- Bot 配置、加密 Key、Web Call、统一历史/指标、错误安全分类。
- AssemblyAI Agent Context 与 Context Carryover。
- Provider-native / Off Turn Detection Source；Off 必须有真实 VAD/固定静音边界，无该 Provider 能力时必须禁用。

## Out of Scope

- 五家 ASR Benchmark/排名与评测页面。
- 8 kHz 电话接入、FreeSWITCH、浏览器采样率选择。
- 自动供应商路由、降级切换、成本优化。
- 真实客户数据跑批或任何付费外部调用。

## Impact

- Affected specs: `bot-config`, `voice-session`, `voice-pipeline`。
- Affected future code: config/session/bot schema and migration, encrypted credential storage, ASR adapters/registry, Bot editor, observability/history, tests。
- UI risk: High；必须执行两个用户 Gate 与三个研发检查点。
