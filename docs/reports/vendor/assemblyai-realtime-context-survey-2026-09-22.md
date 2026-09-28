# AssemblyAI Realtime ASR 上下文能力调研

## 结论摘要

- AssemblyAI 当前适合本需求的接口是 Streaming WebSocket v3：`wss://streaming.assemblyai.com/v3/ws`，模型为 `universal-3-5-pro`。
- 电话音频可直接使用 `pcm_s16le` 或 `pcm_mulaw`，`sample_rate` 支持 8000Hz；音频使用 Binary Frame，建议按真实时间发送 50-1000ms 的 chunk。
- 历史上下文由两部分组成：客户端通过 `agent_context` 传入机器人刚刚说出的文本；服务端默认自动携带最近 5 条已 Final 的用户转写，整体上下文上限为 1750 字符。
- `agent_context` 可在建连时设置，也可在每次机器人回复后通过 `UpdateConfiguration` 动态替换；只对 `universal-3-5-pro` 生效。
- `prompt`、`keyterms_prompt` 与 `agent_context` 是三个不同维度：领域/场景、专有词、上一轮机器人话术。三者可叠加，但评测必须分实验臂，不能混入统一基础榜。

## 推荐接入方式

### 基础连接

- Header：`Authorization: <ASSEMBLYAI_API_KEY>`，不带 Bearer。
- Query：至少冻结 `speech_model`、`encoding`、`sample_rate`、`mode`、语言、Turn Detection 参数和上下文参数。
- 发送：Raw Binary 音频，按墙钟真实时间节奏发送。
- 接收：消费 `Turn`；同一 turn 的新消息覆盖旧消息，只在 `end_of_turn=true` 且 `turn_is_formatted=true` 时保存 Final。
- 结束：发送 `{"type":"Terminate"}`，等待 `Termination`。

### 历史上下文模拟

同一通对话必须复用同一个 WebSocket，并按原始事件顺序回放：

1. 在第一段用户音频前，用 `agent_context` 设置开场机器人话术。
2. 流式发送该用户 Turn 的音频，等待 Final Turn。
3. 在下一段用户音频前，用 `UpdateConfiguration.agent_context` 替换为紧邻的机器人真实话术。
4. 服务端自动保留之前 Final 的用户 Turn；客户端不得把人工标注文本或历史生产 ASR 文本伪装成用户历史。
5. 记录每个 Benchmark 的上下文模式、实际上下文摘要哈希、Turn 序号和响应配置回显。

### 必须设置的实验对照

| 实验臂 | AssemblyAI 配置 | 目的 |
|---|---|---|
| Cold baseline | 单句独立 Session；`previous_context_n_turns=0`；无 `agent_context` | 与其他厂商基础能力公平比较 |
| Agent context only | 单句独立 Session；`previous_context_n_turns=0`；传紧邻机器人话术 | 隔离上一轮机器人问题的贡献 |
| Full conversation context | 同一对话连续 Session；默认 carryover；每轮更新 `agent_context` | 模拟真实多轮 VoiceAgent |

主榜建议使用 Cold baseline；另外展示 Agent context only 和 Full conversation context 相对基础臂的字准率提升，避免把上下文增益误报成纯模型能力。

## 与现有厂商能力的差异

| 厂商 | 实时输入与结果 | 可用引导 | 会话中动态更新 | 当前仓库接入状态 |
|---|---|---|---|---|
| AssemblyAI | Binary PCM；Turn 覆盖更新，Final 后固化 | `prompt`、`keyterms_prompt`、`agent_context`、自动 Context Carryover | 支持 | 尚未接入 |
| Soniox | Binary PCM；Final Token 累加 | `context.general/text/terms` | 不支持，需重连 | 有实时单测/批测；产品 Evaluation 使用 async batch |
| Speechmatics | Binary PCM；Partial/Final Transcript | `additional_vocab`、domain | `SetRecognitionConfig` 不支持动态换词表 | 有实时单测/批测；产品 Evaluation 使用 batch |
| Deepgram | Binary PCM；interim/final Results | `keyterm`/`keywords` | 当前本地规范未证明上下文可动态更新 | 有 Nova-3 实时批测；未进入产品 Evaluation |
| ElevenLabs | Base64 JSON 音频；partial/committed transcript | `keyterms`、首包 `previous_text` | `previous_text` 只能第一包发送 | 有实时单测；产品 Evaluation 使用 Scribe v2 batch |

现有产品 Evaluation 的三家 ASR 用于“完整通话证据生成”，均是文件/异步接口；它们不能直接作为本 Change 的实时对比实现。新评测必须建立独立的 Streaming Adapter 契约。

## 评测设计约束

- 同一实验臂必须使用相同 WAV、相同 8KHz/16bit/单声道输入、相同 20ms chunk 和真实时间 pacing。
- 主指标继续由目标 Benchmark Library 自己的规范化脚本计算；`library_ar` 必须直接使用 `benchmarks/library_ar/asr_char_accuracy.py`。
- 汇总至少包含字准率/CER、WER、空结果率、失败率；实时比较还需记录 TTFT、Final 延迟和实时因子。
- 除通用分数外，必须按语种、方言、场景标签和 Good/Bad 来源切片；上下文实验还要按短回答、数字/账号、专名、歧义词分层。
- 任何付费真实跑批必须在执行前冻结样本数、厂商、模型、预计音频分钟数、费用上限和停止条件，并逐次取得用户授权。

## 官方资料

- [Conversation Context](https://www.assemblyai.com/docs/streaming/universal-3-5-pro/context-carryover)
- [Updating Configuration Mid-Stream](https://www.assemblyai.com/docs/streaming/updating-configuration-mid-stream)
- [Streaming WebSocket API](https://www.assemblyai.com/docs/streaming/api-spec/streaming-websocket)
- [Stream a Pre-Recorded File in Real Time](https://www.assemblyai.com/docs/streaming/guides/stream_prerecorded_file_realtime)
- [Evaluating Real-time STT models for Voice Agents](https://www.assemblyai.com/docs/streaming/evaluations/voice-agents)

## 尚未验证

- 未使用真实 API Key 做连接、阿语识别、8KHz PCM、动态上下文或计费验证。
- 未验证 AssemblyAI 在本项目沙特/海湾阿语数据上的 Context Carryover 收益及多语漂移风险。
- 官方页面没有替代本项目自己的横向基准；所有准确率与延迟结论仍需在相同本地 Benchmark 上实测。
