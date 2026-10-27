# Engineering Assumptions

- Active assumptions: 5
- Last reviewed: 2026-10-21

无产品行为被当作工程假设；实现细节与边界如下。

## A-001 — Source range state is a session-owned Python ledger
- Date: 2026-10-21
- Basis: development-guide B; ASR-01/03 require replaceable snapshots and consumed audio fences.
- Scope: immutable source records and a session-local ledger; no service or dependency added.
- Reversal: replace the internal ledger implementation without changing provider/source/turn contracts.
- Product behavior: unchanged; missing word evidence remains explicitly unavailable and is never reconstructed from string prefixes.

## A-002 — Keep explicit session settings and reuse the locked aggregator
- Date: 2026-10-21
- Basis: numeric values remain uncalibrated, so backend custom TD settings have no silent numerical defaults; Bot drafts and session snapshots use a separate immutable model, leaving ASR provider options intact.
- Scope: reuse Pipecat LLMUserAggregator via a dedicated subclass; aggregate and stop in the same data task to avoid SystemFrame priority races. No dependency added.
- Reversal: internal aggregator factory/model can be replaced while preserving the confirmed APIs and single-authority contract.
- Boundary: current watchdog polls at10ms and diagnoses a100ms media gap; these are provisional engineering values, not calibrated deployment guarantees. Unknown-range transcripts are retained as evidence, never assigned guessed timing. Target-environment validation remains Open.

## A-003 — Immutable inference context and playback evidence ownership
- Date: 2026-10-21
- Basis: D-049/REV-03 and P11 require original source authority and no fabricated client playback.
- Scope: SDK request contexts are snapshotted; once-sent operations settle under explicit timeouts and are shared across Final response versions. The session-local playback arbiter separates queued, sent_unknown, playing and stop_requested, and waits for matching completion before releasing the serial slot.
- Reversal: replace these internal boundaries without changing source/generation validation, successful-operation idempotence or actual client evidence requirements.
- Boundary: arbiter/schema unit tests are not audio transport integration. Legacy numeric playback reports are retained and labeled unverified; no actual rendering is inferred from server messages. No client-render confirmation producer has been connected yet.

## A-004 — Bind identifier operations to proven audio groups
- Date: 2026-10-21
- Basis: NUM-03, ASR-03, D-049 and development-guide B/C/D require shared range ownership, current input validation and original context-version fences.
- Scope: collection keys hash the ordered (epoch, provider source ID, owned start) group; original IDs remain in evidence_ids. Adjacent tails stay separate; newer overlapping groups replace contributions in their original position. Internal input revisions are separate from provider revisions. Each response turn captures its initial keyword gate so Final reanswer cannot gain authority from its own generated reply.
- Reversal: replace the internal key/version representation without changing audio-range, generation, provenance or tool behavior. No new service/dependency or numeric default introduced.
- Boundary: business WPM requires complete actual word coverage; provider window duration and token counts never stand in for speech evidence. Current candidate local revisions can re-enter ordinary TD, but old-candidate correction playback/success-to-new-collection transitions remain unfinished. Echo eligibility records are explicitly not dispatched audio.

## A-005 — Final proof and result delivery are separate state boundaries
- Date: 2026-10-21
- Basis: D-037/D-049 and NUM-03 require confirmed success before a new collection, no repeated effects and truthful failure/current state.
- Scope: retain each applied source text and its current Final proof; capture new-input eligibility at actual speech start. Pure collection succeeds only after TD submission; mixed new provision changes generation only inside a validated operation. Final replay refreshes proof without replaying effects. Before result callback, revalidate current input and project current value/count/generation; superseded operations remain in the audit but do not claim old state is current.
- Reversal: replace internal proof/projection representation while preserving source/generation validation and accurate results. No dependency, external call or runtime numeric default added.
- Boundary: success-path tests do not prove cross-turn correction playback or client acknowledgement. Event cap retains its existing10000 facts plus one explicit truncation marker; this is bounded diagnostic evidence, not full recording retention.

## A-006 — Reuse the production Advanced shell and explicit saved configuration
- Date: 2026-10-21
- Basis: D-047/D-048, frozen v0.14 and M4-5/6 require formal routes/components rather than an acceptance shell; prototype numeric examples are not calibrated runtime defaults.
- Scope: TD/Jev markup and dedicated styles derive from frozen sections but render inside the existing Advanced root; fixture tests replace only API responses. New numeric policy fields are blank; saved policy values round-trip. Preserve saved overflow_pause_ms; for newly enabled completeness use the explicitly entered echo pause as the short overlength pause, consistent with the appendix's allowed pause reuse. No additional server AEC or dependency.
- Reversal: adjust form assembly/adapter without changing saved contracts or the frozen source. Source switching retains the same Bot draft; server requests validate configuration and resource fingerprints.
- Boundary: no complete Checkpoint A/B claim; D-050 now fixes the new-Bot max_calls budget at 100 without a UI control or paid-test authorization. Cache preview/generation and all UI states still need full integration verification.

## A-007 — Preserve audio identity through the locked sender's reconstruction
- Date: 2026-10-21
- Basis: P11 requires matching actual renderer evidence; locked Pipecat BaseOutputTransport reconstructs type(frame)(pcm, rate, channels) and discards instance context_id/metadata.
- Scope: a session task gets an immutable class-bound identity; reconstructed audio uses the existing protobuf name field, without changing PCM/encoding or introducing another transport. A specialized serializer normalizes only those audio subclasses to the existing wire message. No dependency or service added.
- Reversal: replace with a future SDK metadata-preserving sender while retaining identity validation, unchanged samples and client rendering evidence.
- Boundary: native SDK rechunk/flush proof is not client playback. Render-thread worklet currently has fixture tests only and is not mounted in the formal client; actual WS/WebRTC acknowledgements and serial arbiter integration remain required.

## A-R12：复用正式WS输出的异步串行适配层

- 工程选择：在现有TTS任务标记之后、现有transport.output之前加入会话级异步串行处理器；永久缓存直接供同一处理器，不引入第二音频传输或生产依赖。
- 依据：已确认P01—P11的唯一串行播放、真实回执与清空要求；普通生成和缓存准备保持异步，不阻塞ASR/Jev。
- 范围/回退：仅已具备任务协议的正式自建TD WebSocket；WebRTC映射未实现前不宣称兼容。可移除适配层恢复原图，底层缓存与原生/chat路径无迁移。

## A-R15：隔离本地正式页面联调端口
- 工程选择：Vite开发代理允许显式VOICE_AGENT_UI_API_TARGET；省略仍为原127.0.0.1:8000。离线联调使用8765/5174专用端口、/tmp专用存储与health标记，生产构建/接口不变。
- 依据：需要用正式页面验证真实API/持久化，避免占用用户标准配置入口或写入其数据库。外部推理替代且阻断外网；不证明厂商效果。
- 回退：移除开发代理环境参数，继续使用原默认目标；测试数据独立，无业务迁移。

### A-R18：界面语言偏好
- 可回退工程细节：仅localStorage记录voiceagent-td-locale，默认中文；不进入配置/API，存储不可用时切换仍可用。清除此键即可回退默认。翻译只作用界面文本和辅助标签，用户输入及请求数据排除。

### A-R19：锁定SDK待发队列清理适配
- 依据：Pipecat1.8.1 RawAudioTrack._chunk_queue的10ms bytes/Future队列，实际原生输出基线在Interruption后仍留旧PCM。
- 工程细节：仅self_developed WebRTC输出在SDK原生任务取消完成后同步清理待发块并settle等待者；不改PCM/RTP/连接/浏览器播放器或依赖源码。未知队列结构显式失败，不伪报已清理/已停播。
- 影响：仅未发音频，不回收网络/浏览器已缓冲音频。原生TD保留原SDK类。回退为factory custom_td=false即可还原旧输出类；取消缺口随之恢复。

### A-R24：来源位置数字规范
- 同连接内按provider实际时间数值生成内部source ID，去除整数/小数和正负零显示差异；不四舍五入，不跨连接、说话人或不同位置合并，不按文本猜范围。
- 依据：0和0.0对应同一音频位置，原字符串ID会重复追加修订。影响仅运行时内部身份，历史原值不迁移。回退可移除规范函数，但重复来源缺陷随之恢复。

### A-R26：失败快照的来源缓存回滚
- 工程依据：归一化异常返回空，ledger未收到任何片段，内部revision/去重缓存也不得记为已返回。SourceSegment不可变，浅快照可恢复完整旧状态。
- 范围：现有异常捕获路径；不猜时间、不修改正常部分缺范围事件契约，不新增失败降级产品规则。
- 回退：撤销缓存checkpoint/异常恢复与对应测试；无持久化迁移。

### A-R27：按厂商稳定身份保留缺时间证据
- 依据：Flux turn_index/Assembly turn_order在连接内提供稳定来源身份，D-024将时间处理交研发。以epoch+ID保留缺口，不能以其他来源或新连接同ID代替恢复证明。
- 影响：缺口存在时不提交不完整输入、不对不完整候选新发Jev请求；同来源补回可靠范围恢复现有TD流程。未知来源/重连恢复继续未完成，不新增产品降级策略。
- 回退：撤销unresolved_sources与协调器缺口同步；无存储迁移、无架构或UI变更。

### A-R29：已有起点来源缺终点恢复
- 依据：沿用现有Speechmatics speaker+实际start、Soniox实际start来源标识，按D-024自行处理证据完整性；不从文字或收包时刻补时间。
- 范围：epoch内已知起点缺终点及同来源补齐，失败整帧不能清除旧缺口。完全未知身份、非法范围和跨连接恢复仍未完成。
- 回退：撤销新增缺口登记/恢复和对应回归，无持久迁移、UI或架构变更。

### A-R31：尚未完成VAD的输入不算静音证据
- 依据：Delta连续静音/续说撤销以及自测TIME-02/03要求，已收到但尚未分析的PCM不能证明可提交。
- 范围：通过会话分析中计数保护现有提交口，异常/取消按现有未知media语义处理；不改阈值/超时/页面或新增产品策略。
- 回退：撤销计数与try/finally保护，无持久迁移或架构变化。

### A-R32：已入队未处理的音频不算静音
- 依据：TIME-03及M2-1，锁定SDK InputAudioRawFrame为SystemFrame，会排在独立输入队列。使用queue_frame入口登记，不读取/修改SDK私有队列结构。
- 范围：待处理计数与原生callback、异常/清理生命周期；cleanup先取消SDK队列再清本地资源，丢弃未分析PCM不能标健康静音。无阈值/产品流程/架构改变。
- 回退：撤销队列入口跟踪/相关提交保护及测试，无持久迁移。

### A-R34：旧Partial不得使Final来源重开缺口
- 依据：既有来源终态不可降级/迟到隔离契约；时间校验不应先于可证明的已Final来源旧Partial拒绝。
- 范围：六模型当前epoch内已知身份，前置只读终态检查；未知身份不匹配、不改D-049首Final重答，不引入新失败策略。
- 回退：撤销_late_partial前置检查及对应回归，无存储/架构/UI迁移。

### A-R37：保留真实Worklet帧坐标，不据回执收取时间算播放
- 依据：真实历史/播放证据契约及R11时钟待验证项；currentFrame和sampleRate来自实际渲染线程，主线程receipt elapsed属于另一时间域。
- 范围：同一正式WS播放器新增可选原始字段，首帧含内偏移、末帧排他边界、stop为无旧任务输出quantum；每端口随机作用域，认证/格式/同钟校验，历史保留。不同钟/设备呈现时间不自动推算。
- 回退：撤销新增可选字段与显示/回归；旧客户端及旧历史仍兼容，无数据库迁移、传输架构或产品配置控件变更。

### A-R42：连接来源绑定到实际接收任务
- 依据：M1-3及ASR-02要求旧连接迟到事件不能冒充新连接；锁定SDK会由后台任务重试socket或lazy context。
- 范围：以ContextVar保留接收任务原代次，实际连接入口claim避免绕过_connect；不改重试次数/厂商参数/页面，不以到达时间猜音频位置。不代表已验证外部重连或未知范围恢复。
- 回退：撤销Mixin上下文/连接入口包装与相关测试，无数据迁移或架构改变。

## A-R43：未归属缺口与SDK内部超时预算

工程实现：匿名缺口使用内部类型标记，不伪造来源ID/时间；Soniox只信实际SDK整快照作用域。内部setup/cancel预算服从已有显式timeout，清理可跟随但不得默认等待20秒。依据为本地SDK失败回归；不改用户参数或成本上限。回退需保留D-061失败契约及禁止猜来源原则。

## A-R46：显式未知接收上下文

缺少ContextVar连接证据时保留asr_stream_epoch=None，由ASRService作为未归属范围缺口处理，原文保留；不把frame内有效供应商时间戳当作连接身份。依据为ASR来源不可猜测及D-061既有失败契约，不新增产品超时。影响仅self_developed，native不打标签。回退可调整上下文传递适配但不得恢复猜当前连接或静默丢弃原文。

## A-R47：固定单元保持精确请求文本

锁定Pipecat Flux sentence模式默认追加尾空格以分隔连续句子；独立单元没有后继句子，单元合成实例关闭_append_trailing_space，保持已授权及配置的精确文本/字符预算。仅新建单元处理器，不修改普通回复处理器；可通过该实例文本准备适配回退，但不得放宽授权守卫或静默增加发送文本。已用真实SDK离线协议替身验证。

## A-R49：已知PCM率的采样范围比较

D-062窗口终点2.6399999秒与词终点2.64秒在正式16kHz PCM下包含相同采样，不是缺字段。以半开区间[start,end)对应[ceil(start*fs),ceil(end*fs))进行包含/消费/Final切分比较；乘法整点仅沿用4 ULP机器噪声处理，原始时间不改写。不设固定毫秒容差，不推断供应商float32，不在未知率/跨连接时钟上套用。采样率只由已验证AudioConfig→ASR factory提供；未取得率仍严格拒绝该差。为可回退内部表示修复，不改UI/外部成本/等待契约。回退需恢复严格未知而非猜来源；实际回包和跨提交必要不变量已先红后绿，真实修复后仍未调用。证明见verification/development-20261023-r49/asr-boundary-design.md。

## A-R58：隔离候选用单包解码完成屏障关联输出
- Status: Engineering assumption; native confirmation pending
- Basis: 真实D-066字段证明微秒标签可差1us；不以固定时间容差放行。WebCodecs AudioDecoder.flush在完成之前发出已有队列输出（https://www.w3.org/TR/webcodecs/#dom-audiodecoder-flush）。一次只提交一个已验payload的包，收齐该job的恰当48k/960输出后才按原生source interval标任务。
- Scope: D-064隔离候选，正式链路未选用；原生Opus跨flush状态、额外耗时未验证。
- Rollback: 撤回候选job适配并保持候选停止/正式旧播放器，不能回退为伪报播放或猜微秒近邻。

## A-R70：本地同输入播放对照的测量边界

仅开发测试插入同一采样阈值AudioWorklet观察器，原链通过MediaElementAudioSource接观察器，候选在任务Worklet输出接观察器；记录浏览器收到首个bot-started-speaking控制事件至首个非零输出量子、及点击到首输出，全部浏览器时钟。原链新增WebAudio观测桥可能改变缓冲/启动成本，因此只报告带此仪器的本地对照，不作为未改动HTML播放器精确新增E2E、硬件播放或P95。真实物理/手机/弱网延迟保持未验证。不改生产页面/默认配置/费用；可撤去测试文件回退。

A-R70测量更新：原MediaElementAudioSource观察桥未取到输出，已停止，最终使用HTML captureStream只读支路→零增益观察器，不重新路由原HTML音频；捕获桥延迟未校准，仍不证明精确新增E2E或P95，详见r70。

## A-R77：因果时钟账本资源保护
- Date: 2026-10-25
- Scope: D-073工程实现。
- Assumption: 仅以同一Worklet上下文严格frame前后顺序关联服务端挑战发出/接收边界，不假设上下行延迟相等、不线性外推物理时间。每会话8 pending/32锚、2秒过期用于内存与过旧证据保护，达界明确缺失而非猜值。
- Basis: 认证挑战因果顺序；Web Audio currentFrame为同上下文处理块坐标。见r77报告。
- Impact: 可能范围较宽或过期缺失，不改变音频传输、播放仲裁或收费。不以Worklet时间证明声学出声。
- Rollback: 停用时钟端点/客户端采样，保留既有实际任务事实和明确缺失，不迁移或回算旧历史。


### r81：源端因果证据冻结（工程细节）
- Date: 2026-10-25
- Scope: D-073，正式WS输入身份与时钟。
- Assumption: 只复用既有16k单声道输入样本和配置VAD源终点；原SDK转换/分包保持不变。输入、输出nonce完全隔离，源证据在候选暂停时冻结，未提交续说丢弃；64候选和4096输入跨度为可回退内存预算。
- Basis: 正式浏览器PCM来源包、配置VAD audio_ms及实际Worklet挑战证据；r80/r81。
- Impact: 缺锚/断层/采样率不一致仍缺失，范围可能宽；不证明ADC或硬件出声时间，不改变产品终点/失败/收费规则。
- Rollback: 停用输入来源封装/采样与区间合成，保留原音频及显式缺失；不改旧历史。


### r82：冻结样式作用域与标题遮挡修复
- Date: 2026-10-25
- Scope: 正式Sessions列表/抽屉的Checkpoint A。
- Assumption: 复用冻结的td-content/td-history局部作用域，按现有td_commit/候选/本地收集显示状态，不推测播放；为正式DOM包装增加8px内容padding以避免已证明的sticky头遮挡。这是可回退工程修复，不修改原型设计或产品流程。
- Basis: 正式/冻结计算样式差异和title.y=67<header.bottom=75红灯；修复后title.y=89、头bottom=75。
- Impact: 正式Sessions字号/层级恢复基线、首标题可见；D-072手机全局列表顺序不变，旧历史数值/原文不变。
- Rollback: 回退本轮Sessions局部class/样式/标签，冻结文件始终只读；回退会恢复已登记的显示缺陷。

### r86：受控RTC上行坐标旁路
- Date: 2026-10-25
- Scope: D068开发候选的原生SmallWebRTC输入路径，仅采样来源诊断。
- Assumption: 保留原receiver/decoder/resampler与全部PCM，旁路记录实际编码payload hash、原RTP timestamp/SSRC、原生decoder PTS和processed PTS/样本数；缺口严格未知，不拿服务器收件时间补采集时间。这是可回退工程证据补齐，不改变VAD/提交/播放/费用规则。
- Basis: 锁定SDK read_audio_frame使用processed PCM但写入frame.pts；需要独立processed时间基证明，不能从当前字段猜范围。
- Impact: 仅开发候选多保留有界metadata/哈希，开销和浏览器join尚待后续实际验证；无新依赖，不默认采用、不改变原音轨。
- Rollback: 去掉开发候选安装调用，原音频与缺失指标保持。

### r86：RTC sender元数据旁路
- Date: 2026-10-25
- Scope: D068受控开发RTC及D073来源计时前置证明，默认RTC不启用。
- Assumption: 在既有RTCRtpScriptTransform能力下观察sender编码帧的SSRC/RTP timestamp/captureTime和payload hash，立即原样放行同一frame；哈希与元数据上报不等待音频，最多8条未ack证据，关闭后销毁worker。没有换codec/track/麦克风或传输。
- Basis: W3C Encoded Transform定义captureTime来自采集时钟且相对本worker Performance.timeOrigin，不能拿观察时间代替；服务器映射已通过本地实际RTC。
- Impact: 仅开发候选增加有界旁路开销，端到端新增延迟和跨浏览器仍未验证；字段缺失就缺证据，不降级猜测。
- Rollback: 移除sender旁路绑定，原RTP与显式缺失指标不变。

### r87：认证RTC源时间与有界区间关联
- Date: 2026-10-25
- Scope: D068开发候选、D073保守范围；不启用默认RTC、不改音频。
- Assumption: 使用同sender worker Performance坐标的16k刻度响应既有capture-clock挑战；原生captureTime按精确二进制值转有理数，只在已证实同包/processed样本范围内定位，向下/上取整形成刻度包络，不舍入成伪精确值。原生报告时间不冒充物理ADC/声学；两端严格因果锚仍决定范围。
- Basis: r86同包匹配与W3C captureTime时钟域；CallCapture既有源边界冻结/播放锚及D073无RTT对半规则。
- Impact: 新会话/连接epoch隔离；待关联PCM/packet证据有界且2秒超期作缺失，无缺包插值/跨时钟补值/收费。只增加认证元数据协议和历史证据，不新增配置控件。
- Rollback: 停用源元数据上传/关联，原音频及显式缺失保留；旧已保存历史不改。

## r88工程修复（2026-10-26）
- 独立词段拼接补词边界，Soniox连续subword由来源标志保留厂商空格；跨提交/Final切片先完整覆盖校验，再取原文范围，不按缺失词表重建文本。无新词法产品分流。
- 回执HTTP 3秒截止、关闭取消，服务端stop控制发出后独立5秒确认保护；均为失败保护工程预算，不延长普通TD/编号等待，不能伪造停止后继续播放。错误遥测不阻塞媒体清理。可回退独立sender模块/guard，但回退将恢复本次评审故障，因此不得作为验收方案；默认RTC候选开关保持不采用。
- 无费用/厂商/新依赖/传输架构变更。严格RTC E2E缺失失败保留，不通过禁用严格断言把它改称通过；播放/Final范围单独验证，不替代源指标闭环。

## r90界面工程修复（2026-10-26）
- 固定fixture只经过API数据适配，正式路由/组件/DOM不变；冻结HTML只读对比。650/701补断点边界，不更改基线。
- 非模态Jev/组件/Sessions跳转为键盘设置可见目标，返回原触发控件；异步历史响应仅当用户未移动焦点时转移。不加模态焦点圈，不改业务规则。可按局部补丁回退，但会恢复已确认焦点缺陷。
- 无新依赖、后端/媒体/收费调用或产品规则变化。专项计划为未授权方法清单，不能按文档自动调用厂商。

## r94 Flux取消边界工程修复（2026-10-26）
- 依据Deepgram官方Interrupt协议及锁定SDK无speech_id二进制入口，两条旧包归属/提前Speak失败复现确认工程缺陷，不重问D049取消产品规则。
- 取消确认总截止2秒自取消发起计，独立有界发送不阻塞本地Interruption控制；新Speak等待确认，失败永久错误而不是重连猜测。该预算是服务故障保护，不改TD最长静音或新增配置字段；可能增加取消确认往返，真实分布待单批验证。
- 回退应逐块移除取消屏障并恢复旧适配器，但会恢复确认缺陷，不作为可验收替代；不改音频传输/原型、依赖或默认RTC采用。

## G2-02历史展示工程返修（2026-10-26）
- 有编号本地采集、已配置提醒或跟读准备事实的已归属轮次视为可展示内容；沿用原事件分组/渲染，不造普通用户提交、LLM调用或延迟值。依据已冻结历史契约和独立缺陷报告，非新增产品决定。
- 不改后端/媒体/原型，旧历史无新事件时沿用现有fallback。可回退这处分支补丁，但会恢复漏展示缺陷。
