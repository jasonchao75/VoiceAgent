# TD 输入契约补充：各 ASR 的 Partial / Complete 映射

核对日期：2026-10-20。范围为当前注册的四家、六种模型：Deepgram Flux 英文 / 多语种、Nova-3、Speechmatics enhanced、Soniox stt-rt-v5、AssemblyAI universal-3-5-pro。

**本文区分官方事件含义、当前代码行为和自建 TD 的目标需求。仅做官方文档与锁定依赖的静态核对，未调用厂商、未回放真实音频，不代表这些映射已经接入。**

## 1. 三件事必须分开

| 概念 | 含义 | 能否直接提交给 LLM |
|---|---|---|
| ASR Partial / Interim | 当前范围的转写仍可修订；新快照覆盖同一范围旧快照 | 不能；可作为 Jev 输入与等待超时后的最新文本 |
| ASR Complete / Final | **某个音频范围**的转写已确定，可能只是一小段，不保证整轮说完 | 不能；先纳入文本缓存，仍由 TD 决定提交 |
| TD 交出话轮 | 本地人声状态、优先规则、Jev 和等待保护共同决定提交当前用户内容 | 只有自建 TD 的一次最终提交信号可触发 LLM |

另有两种同名概念不可混淆：Jev Choice 的 `complete` 是“用户表达看起来已完整”的分类，**不是** ASR Final 标记；Pipecat `TranscriptionFrame.finalized` 是框架内部 finalize/收口状态，**不能单凭它为所有厂商判断文本是否稳定**。

建议文档统一称“转写状态 Partial / Final”，保留 Complete 作为 Final 的产品别名；不增加第三种转写状态。一个当前 TD 候选可能包含“已确定前缀＋仍可修订尾部”，此时整体仍是 Partial。

## 2. 厂商事件 → 统一输入

下表最后一列均针对 `self_developed` 模式。厂商原生或 Off 的现有轮次策略不在此处改写。

| 厂商 / 事件 | 文本状态及范围 | 缓存怎么更新 | 自建 TD 如何处理 |
|---|---|---|---|
| Flux `TurnInfo.event=Update` | Partial；当前 `turn_index` 的累计文本快照 | 替换该厂商 turn 的可变快照，不逐条追加 | 更新 Jev 可读取的最新文本；不直接提交 |
| Flux `EagerEndOfTurn` | 提前结束预测，按 Partial 处理 | 同一 turn 更新候选快照 | 不能当最终转写或直接启动普通回复；当前工厂未启用 eager |
| Flux `EndOfTurn` | Final；该厂商 turn 的完整文本 | 锁定对应 turn；后续其他 turn 可继续属于同一 TD 用户轮 | 仅表示厂商文本收口；不得越过自建等待 / 编号收集规则 |
| Flux `StartOfTurn` / `TurnResumed` | 人声 / 续说事件，本身不代表新增 Final | 不创建重复文本；有文本时按其实际类型更新 | 保留为人声诊断；续说保护以本地 VAD 为准，不以厂商停止事件替代本地计时 |
| Nova-3 `Results.is_final=false` | Partial；当前结果音频范围 | 替换未确定尾部，保留此前已确定分块 | 给 Jev 的是合并后的当前 TD 文本，而非仅这一包 |
| Nova-3 `Results.is_final=true` | Final；当前分块，不一定是整轮 | 将该范围并入稳定前缀，移除它覆盖的旧 Partial | 不提交 LLM；`speech_final` 另行判断端点含义 |
| Nova-3 `speech_final=true`、`UtteranceEnd` | 厂商静音端点；不应单独推导 `is_final=true` | 若同包带文本，仍按 `is_final` 入库；端点另记 | 仅作为边界候选 / 诊断；空端点不能清空已有文本 |
| Speechmatics **当前 Voice SDK** `AddPartialSegment` | Partial；`segments[]` 内各说话人 / 片段的可变文本 | 按片段位置、说话人和版本替换，不能把每次完整快照追加 | 更新当前用户文本 |
| Speechmatics **当前 Voice SDK** `AddSegment` | Final；一个或多个确定片段 | 对每个片段去重入库；片段后仍可能有同一 TD 用户轮的内容 | 不等于 `EndOfTurn`，尤其启用句子分段时 |
| Speechmatics Voice SDK `EndOfTurn`、`EndOfUtterance`、`EndOfTurnPrediction` | SDK / 厂商边界或预测，不是通用文本 Final | 若无转写载荷，不生成文本 | 不直接提交；不能把本地 SDK 的 TD 误写成云端 API 事件 |
| Speechmatics **底层 Realtime API** `AddPartialTranscript` / `AddTranscript` | 前者 Partial，后者 Final 分块 | Partial 覆盖上次 Final 后的可变范围；Final 分块依次合并 | 这是底层协议说明；当前 Pipeline 实际消费的是上面的 SDK Segment 层 |
| Soniox 普通 token `is_final=false` | Partial token | 替换本次可变尾部 | 不能追加每次尾部快照 |
| Soniox 普通 token `is_final=true` | 已确定 token，未必结束整个语音片段 | 累计稳定 token，再拼当前可变尾部；token 可能是子词 | 不能把“某个 token Final”提升为“整轮 Final” |
| Soniox 特殊 token `<end>` | 自动端点，前序片段已收口 | 结束该厂商片段；过滤标记，不放入用户文本 | 只更新文本完整性与端点元数据，不直接提交 LLM |
| Soniox 特殊 token `<fin>` | 手动 finalize 的完成确认，**不是用户主动交出话轮** | 按请求范围收口，不拼入文本 | 仅唤醒相应 Final 等待；无匹配请求也不能产生新的提交 |
| AssemblyAI `type=Turn, end_of_turn=false` | Partial；当前 `turn_order` 的累计 `transcript` | 同 turn 替换快照，不逐条追加 | 即使部分 `words[].word_is_final=true`，也不能把整轮标成 Final |
| AssemblyAI `type=Turn, end_of_turn=true` | Final；该厂商 turn 的完整 `transcript` | 锁定 / 更新对应 turn，格式化重发不重复追加 | 在自建 TD 中只收口文本，不取得最终提交权 |
| AssemblyAI `turn_is_formatted`、`utterance` | 前者表示格式化；后者在部分协议 / 模型中为停顿时的子片段 | 完整快照以 `transcript` 为准；不能把 `utterance` 当整轮追加 | 不能只凭 formatted 或非空 utterance 判定用户结束 |
| 各家连接完成 / `Begin` / `Connected` / `EndOfTranscript` / `Termination` / `finished=true` / Error | 连接生命周期或错误，不是用户转写 Complete | 保存诊断；是否有尾部文本须由实际文本事件决定 | 不伪造正常交出话轮；保持现有错误处理，断线处理不在本表中重新定义 |

事件依据：[Flux API](https://developers.deepgram.com/reference/speech-to-text/listen-flux?explorer=true)、[Flux eager lifecycle](https://developers.deepgram.com/docs/flux/voice-agent-eager-eot)、[Nova streaming](https://developers.deepgram.com/reference/speech-to-text/listen-streaming)、[Speechmatics Voice SDK](https://docs.speechmatics.com/integrations-and-sdks/voice-sdk)、[Speechmatics Realtime](https://docs.speechmatics.com/speech-to-text/realtime/quickstart)、[Soniox endpoint](https://soniox.com/docs/stt/rt/endpoint-detection)、[Soniox manual finalization](https://soniox.com/docs/stt/rt/manual-finalization)、[AssemblyAI U3.5 示例](https://www.assemblyai.com/docs/streaming/migration-guides/gladia-to-aai-streaming)、[AssemblyAI 消息序列](https://www.assemblyai.com/docs/streaming/message-sequence)。

**版本约束：** Speechmatics 官方现已推荐新的 Agent STT，但本项目锁定 `speechmatics-voice==0.2.8`；不能将新协议的 `segment.transcript` 单对象套用到当前 SDK 的 `segments[].text`。本需求不自动迁移 SDK。[两代接口区别见官方 Voice SDK 说明](https://docs.speechmatics.com/integrations-and-sdks/voice-sdk)。AssemblyAI 当前固定 `universal-3-5-pro`；不套用其他模型的置信度阈值 / 格式化参数行为。

## 3. 当前代码与需求之间的差距

静态依据为 `pipecat-ai==1.8.1`、`speechmatics-voice==0.2.8`，依赖文件与本地安装元数据一致。以下是当前行为，**不是自建 TD 已完成的证明**。

| 服务 | 当前 Pipecat / 项目代码行为 | 自建 TD 实现时必须补的环节 |
|---|---|---|
| Flux | `stt_base._handle_update()` 仅调用 `on_update`，未产生 Interim frame；项目没有订阅这个回调。`EndOfTurn` 才发送 Final frame 并广播停止建议 | 衔接 Partial 回调；若需要逐词时间戳和 turn/sequence 元数据，还须在原始事件层保留，回调仅文本不够 |
| Nova-3 | `is_final` → TranscriptionFrame，其他非空结果 → Interim；项目子类额外在 `speech_final` 广播 ProposedUserStoppedSpeakingFrame | 复用文本分块；自建来源隔离原生停止建议。不能只看 frame.finalized，普通 is_final 分块不一定置该值 |
| Speechmatics | AddPartialSegment → Interim；AddSegment → TranscriptionFrame；EndOfTurn → 停止建议。SDK 控制分段，可能延迟最终片段产生 | 保留 Segment 范围、说话人与时间戳；避免重复运行旧 SMART_TURN；外部 finalize 如何配合自建模式需适配验证，不自动迁移新 Agent STT |
| Soniox | 普通稳定 token 仍缓存在 Interim 中；仅收到 `<end>` / `<fin>` 才输出 finalized TranscriptionFrame 并提出停止建议 | 需要从 token 元数据区分稳定前缀和可变尾部；过滤控制标记；自建来源拦截停止建议 |
| AssemblyAI | 先检查 end_of_turn；若框架开启 format_turns，还等 turn_is_formatted；Final frame 后广播停止建议，其余为 Interim | 自建来源拆开“文本 Final”和“轮次停止”；同一 turn 的格式化更新覆盖而非追加；不要把框架等待格式化误解成厂商 EOT 定义 |

代码定位（仓库相对路径）：

- `src/asr/factory.py`：注册六模型、Nova speech_final 子类及其余服务构造；`src/asr/config.py`：当前 Catalog 与 Partial 配置。
- `.venv/lib/python3.13/site-packages/pipecat/services/deepgram/flux/stt_base.py`：`_handle_update`、`_handle_end_of_turn`。
- 同目录下 `deepgram/stt.py`、`speechmatics/stt.py`、`soniox/stt.py`、`assemblyai/stt.py`：具体转写 frame 与停止建议映射。`.venv` 仅为本次静态证据位置，不应提交依赖源码。

另发现原型 AssemblyAI 使用了 `universal-streaming-multilingual` 示例，而实际项目注册为 `universal-3-5-pro`。这是原型与代码的工程偏差，已登记任务；本表以当前注册为准，不把它当成用户需要重新选择模型的产品问题。

## 4. TD 应消费的统一文本视图

保持 TD 简单：各适配器负责解析差异，TD 不直接写五套原始协议分支。以下为需求字段，不要求新增独立服务。

| 信息 | 用途 |
|---|---|
| provider / model / stream_epoch | 标识来源与连接代次；重连后时间和序号不能与旧连接混用 |
| source segment / turn id、source sequence（若有） | 识别覆盖范围，抑制重复和过期事件；缺厂商 ID 时由适配器结合位置维护本地范围，不能只按文本去重 |
| revision、稳定前缀、可变尾部、合并后的 transcript | Jev 使用合并后的当前用户文本；同一范围 Partial 替换，不重复追加稳定片段 |
| transcript_status=Partial / Final | 说明当前**所需候选范围**是否仍有可变 / 未确认尾部；与 Jev speech_state 分离 |
| words / tokens 的原始文字、起止时间、来源与可靠性 | 编号归一化和 WPM 的证据；缺少可靠时间戳不能凭消息接收时间或均分 token 虚构 |
| source endpoint 类型、finalize 请求关联、处理进度（若提供） | 区分厂商自然端点、应用主动收口和流关闭；不因此触发 LLM |
| TD candidate id、候选对应的音频边界 | 保证迟到的 Final 只能满足对应候选，旧 turn 的 Final 不能误结束新用户内容 |

`Final` 的判断不仅要看最新一包：已确定旧片段后若仍有新 Partial，整个候选仍是 Partial；一份覆盖旧范围的迟到 Final 不能清除较新的尾部。厂商可在一个 TD 用户轮中产生多个 turn，必须按顺序合并；相同内容在不同位置重复念出是合法输入，不能按字符串全局去重。

时间统一为“本连接音频起点起的毫秒”，再映射到本地音频时钟：Flux / Nova `words.start/end` 为秒；Speechmatics 元数据和词结果 `start_time/end_time` 为秒；Soniox `start_ms/end_ms` 与 AssemblyAI `words.start/end` 为毫秒。保留原始精度；重连显式换代，不拿 wall-clock 接收时刻算 WPM。[Soniox 时间字段](https://soniox.com/docs/api-reference/stt/websocket-api)、[Speechmatics 段时间](https://docs.speechmatics.com/integrations-and-sdks/voice-sdk)、[AssemblyAI words](https://www.assemblyai.com/docs/streaming/message-sequence)、[Nova words](https://developers.deepgram.com/reference/speech-to-text/listen-streaming)。

## 5. 嵌入现有自建 TD 流程

1. 音频持续送现有 ASR 与本地 Silero VAD。ASR 到包只更新缓存；不能“每包 Partial 都新增一段用户文本”。
2. 本地 VAD 确认候选停顿后，读取当前 TD 候选的“稳定前缀＋最新尾部”，先执行关键词窗口及严格全输入编号校验；只有纯编号本地收集，带前缀/提问/更正等混合表达整体连同机器人上下文送Jev，再由对话LLM调用编号工具。只拿厂商最后一包可能漏掉前面 Final 分块。
3. ASR 后续修订时更新版本；结果不得跨候选或覆盖范围误用。若 Jev 所依据文字已发生实质变化，其结果按已有版本有效性约束失效；重判、合并和请求限额的具体节流归工程校准任务，不能绕过最长等待。
4. TD 确定可提交后，若对应候选已 Final，提交缓存中的**整个待提交用户范围**；否则仅等待配置的 ASR Final 时间。收到旧片段 Final 不算本候选完成。
5. Final 等待到期使用最新非空合并文本；普通路径仍受同一个最长静音截止约束，不能再加一段固定等待。用户续说取消本次待提交。
6. 处于编号未满位收集时，执行已确认的独立收集保护，不被普通 semantic TD 截止提前提交；厂商 EOT/Final 也不能越过这条规则。编号提醒后保留，超位提醒优先，更正请求清空；见D-028、D-031、D-032。
7. 迟到的重复Final/格式化包不能再次触发LLM或重复跟读；但ASR对已播片段发生实际内容修订时，按用户确认补读更正内容，记录修订版本，避免重复修订包反复入队。用户主动局部更正则调用清空工具。

**不在本次文档中写死主动 finalize 策略。** Flux 的 ForceEndTurn、Nova 的 Finalize、Speechmatics SDK finalize、Soniox finalize、AssemblyAI ForceEndpoint 均可能影响厂商分段和返回顺序；若采用，必须在对应适配器显式关联请求与音频范围，并服从同一 Final 等待预算。它们是获取确定转写的控制手段，不是第二套交出话轮判定。当前需求的短等 Final 超时回退无需依赖每家均支持同样的主动控制。[Flux 控制事件](https://developers.deepgram.com/reference/speech-to-text/listen-flux?explorer=true)、[Nova 控制事件](https://developers.deepgram.com/reference/speech-to-text/listen-streaming)、[Soniox 手动确认](https://soniox.com/docs/stt/rt/manual-finalization)。具体调用方式尚未实现 / 验证。

## 6. 验收场景补充（待实现）

| 场景 | 期望 |
|---|---|
| 多次累计 Partial：1 → 12 → 123 | 缓存为 123，而不是 112123；重复包不重复跟读 |
| Final 分块 123 后出现新 Partial 45 | 当前文本为 12345，整体仍 Partial；后续 Final 456 覆盖尾部得到 123456 |
| Soniox 部分稳定 token 与非稳定 token 混合 | 保留稳定前缀、替换可变尾部；不得整包强制 Final |
| ASR 原生 EOT 先到，Jev / 本地规则仍要求等 | 更新缓存，不提交 LLM；厂商片段边界不清空本地待提交内容 |
| 旧片段 Final 在新 Partial 后迟到 | 只收口其覆盖范围，不将新内容误标 Final，不提前解除 Final 等待 |
| ASR Final 超过配置等待 / 最大截止 | 最新非空合并文本仅提交一次；迟到结果不再次触发普通回复 |
| VAD 在 Final 等待中检测到续说 | 撤销候选，继续收集；不因为厂商 Final 已到就抢话 |
| 编号目标 16 位，厂商仅对前 3 位发 EOT | 3 位可按规则跟读；编号仍未满，继续按独立收集保护等待 |
| formatted 重发或控制标记 / 空端点 | 不追加重复文本，不把标记送 Jev，不因空包丢弃已有内容 |
| 重连、时间戳缺失或说话人切换 | 连接范围不串用；保留来源及缺失标记，不能用墙钟或平均分配时间伪造 WPM |

## 7. 证据边界

- 已核对：当前注册模型、锁定依赖及实际转写 / 停止事件代码；上述官方协议与当前 SDK 层差异。
- 未验证：厂商实包顺序、Partial 频率、逐词时间覆盖、控制消息收口延迟、不同语种及噪声下的表现；需后续获授权测试。
- 待实施：Flux Partial 桥接、统一缓存 / 版本 / 时钟、self_developed 单一提交权、Final 等待及编号状态机。事件表不替代这些实现与测试。

## 8. 时间戳可用性专项核查（2026-10-20）

这是工程调查和验收项，不是要求用户判断厂商是否有时间戳。结论仅到“官方字段 / 锁定代码”，不把文档存在当成每条真实Partial都有可用时间。

| 当前模型 | 官方 / SDK音频时间证据 | 当前框架到Pipeline保留情况 | 工程结论 |
|---|---|---|---|
| Flux 英文 / 多语种 | TurnInfo 的 words[].start/end（秒），audio_window_start/end；官方EndOfTurn示例明确提供 | Final的result=data保留原事件；Update仅on_update文本回调，项目未桥接 | 支持；必须补原始Update及时间元数据传递。尚不保证每个Partial都有足够词级时间 |
| Nova-3 | Results.channel.alternatives[].words[].start/end（秒），结果start/duration | Interim/Final frame的result=message保留结果对象 | 字段已能进入frame，需对实际边界、空words和时钟做定向验证 |
| Speechmatics enhanced（Voice SDK0.2.8） | segments[].metadata.start_time/end_time（秒）；include_results开启时另有fragments[].start_time/end_time | Pipecat1.8.1 attr_from_segment只读取segment.get('results',[])，未转传metadata；当前SDK模型用fragments字段，构造中未显式开启include_results（SDK默认False） | 厂商/SDK有时间；当前适配层存在静态字段不匹配，不能宣称可直接计算WPM。需保留段metadata，必要时启用并转传fragments |
| Soniox stt-rt-v5 | 普通token.start_ms/end_ms（毫秒）；字段可选，翻译输出不含；控制token不作为发音单元 | Interim/Final的result保留token列表 | 支持源转写时间；逐项检查字段存在，不能要求<end>/<fin>有发音时间 |
| AssemblyAI universal-3-5-pro | Turn.words[].start/end（毫秒）；模型Partial频率不同 | 当前服务Interim/Final都将message作为result保留 | 支持；需按固定模型实测Partial覆盖和word序列，不借用其他模型的输出频率承诺 |

官方依据：[Flux](https://developers.deepgram.com/reference/speech-to-text/listen-flux)、[Nova](https://developers.deepgram.com/reference/speech-to-text/listen-streaming)、[Speechmatics段时间](https://docs.speechmatics.com/integrations-and-sdks/voice-sdk)、[Soniox可选时间字段](https://soniox.com/docs/api-reference/stt/websocket-api)、[AssemblyAI消息词时间](https://www.assemblyai.com/docs/streaming/message-sequence)。Speechmatics fragments/include_results及适配不匹配依据锁定依赖 `_client._emit_segments`、`SegmentMessageSegment`、Pipecat `_send_frames.attr_from_segment`，不是对新Agent STT的推测。

验收由工程负责：源事件→frame.result→统一TD输入逐层核对时间范围/单位/文本关联；使用固定fixture检查缺字段、空列表、修订、重连和控制token。真实回包仍需获授权测试。片段只要有覆盖完整目标内容的可靠首尾时间就可计算整体WPM；跨范围无法定位时不得均分或拿墙钟伪造。缺证据时不满足“WPM低于阈值”的必要条件，因此不触发该次慢速跟读，保留正常转写与诊断。

## 9. 转写修订与播放队列：已讨论内容与剩余边界

已确定：同一片段重复Partial不得重复计数或跟读；不同音频位置重复念相同数字保留；用户续说不会取消正在播放的跟读。用户主动清空/更正/询问走普通对话路径，收集状态由Pipeline提供给LLM；具体清空工具仍为方案、未实现。

工程实现建议（不伪标用户确认）：待播放片段绑定收集代次/源范围/revision，播放前采用有效版本；单路输出串行排队，不让两段机器人跟读同时叠播。多段序号、去重、旧候选作废属于工程任务。用户语音可与机器人跟读并行，不等于机器人音频彼此并行。

当前已确认：已播出123后，ASR将同一音频改成124，需要补读更正内容；记录原播文本、修订文本和补读结果，不覆写原播放事实。同一修订版本的重复包不重复补读。用户主动说“把第三位改成4”则是另一条路径：第一版直接清空已有编号，不做局部替换或先追问。工程仍需实现并发/版本隔离，不能把规则确认当作测试通过。

## 2026-10-22 来源范围恢复的实际实现证据

以下为研发实现与fixture契约，不代表真实六模型兼容通过：

| 模型/来源 | 连接内身份 | 缺少/非法范围的处理 | 恢复证明 |
|---|---|---|---|
| Flux general-en / general-multi | 厂商turn_index | 已知ID但缺时间或时间非法，保留epoch+ID缺口 | 同epoch、同ID重新提供可靠窗口/词时间 |
| Nova-3 | 实际start的规范数值 | start已知但duration缺失不默认0；非法duration保留缺口 | 同epoch、同start恢复可靠duration |
| AssemblyAI | 厂商turn_order | 已知ID但词时间缺失/非法，保留缺口 | 同epoch、同ID提供可靠词范围 |
| Speechmatics | speaker_id+实际start | 起点已知但终点缺失/非法，保留缺口 | 同epoch、同speaker/start提供完整范围；完整fragment可提供实际边界 |
| Soniox | 实际start_ms | 起点已知但终点缺失/非法，保留缺口 | 同epoch、同start_ms提供可靠终点 |

缺口存在时，后续其他已知来源不能掩盖它而触发不完整普通提交；当前缺口变化同步候选并取消旧语义判断，不为不完整候选新发Jev请求。恢复后按实际来源时间排序并沿用唯一提交权，不将恢复当新用户轮次。

归一化整帧异常时，尚未返回给ledger的内部revision/去重缓存回滚，已经存在的缺口不能被该失败帧误判恢复。非法行已有可靠身份时仍保留该行缺口。测试对应`test_stable_source_missing_time_blocks_other_sources_until_same_id_recovers`（六模型×缺时间/非法时间）与`test_rejected_snapshot_does_not_consume_valid_sibling_revision`（两家×已有来源/初次来源×此前是否缺范围），红绿日志见verification/development-20261022-r30/。

仍未实现/证明：完全未知身份/起点的可靠归属和恢复、跨连接时钟和旧缺口恢复、真实回包/时间覆盖。新连接同ID不能自动清旧epoch缺口。不从相似文字、文本长度、收包时刻或静默超时猜音频归属。普通fixture通过不代表这些未验证范围通过。

模型ID证据更正：r33对新增范围回归加入正式Catalog校验，并更正Soniox/Assembly旧参数；目标型号与历史日志适用边界见[更正说明](../verification/asr-model-evidence-correction.md)。历史r27～r32的两处旧型号fixture不能当作目标型号配置覆盖。

## r49采样边界比较（工程表示，不是时间戳重写）

正式factory把已知输入PCM率带入SourceNormalizer/SourceSegment。原始毫秒值、词时间、来源范围均保持；包含/消费/迟到Final解析仅在该已知率的同连接音频上比较实际半开采样区间。D-062的2.6399999与2.64秒在16kHz下都以42240为排除边界；2.6400001秒已经纳入下一样本，仍必须拒绝。未知率使用原严格比较，跨连接绝对时钟仍未解决；不使用固定毫秒容差。推导/证据见verification/development-20261023-r49/。
