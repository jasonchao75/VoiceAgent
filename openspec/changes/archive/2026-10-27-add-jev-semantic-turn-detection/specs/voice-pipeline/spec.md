# Delta — 已确认规则，待实现与验证

## ADDED Requirements

### Requirement: Jev semantic turn mode
新增自建模式 MUST 在本地运行 Silero VAD，通过 Jev 云端接收上一轮机器人文本及当前用户 ASR 转写的语义判断，不部署本地语义或声学 TD 模型。原有模式 MUST 保持可用。

#### Scenario: Candidate pause
- **WHEN** VAD 确认候选停顿且有当前转写
- **THEN** 系统异步请求 Jev，统一 TD 策略结合结束概率和结构化标签判断等待，而不是由 Jev 直接触发 LLM

### Requirement: Bounded silence and cancellation
系统 MUST 把最短与最长等待定义为连续静音区间，以同一音频时序计时；VAD 和云端调用的已耗时间 MUST 计入总等待。

#### Scenario: Valid result arrives
- **WHEN** 有效 Jev 结果到达，且用户没有续说
- **THEN** 系统只等待目标总静音中尚未经过的部分，并遵守最短边界

#### Scenario: Speech resumes
- **WHEN** VAD 确认用户恢复说话
- **THEN** 系统撤销候选提交并丢弃该候选所有迟到语义结果，开始下一次停顿检测

#### Scenario: Transcript revision
- **WHEN** Jev 判断所用转写已被更新
- **THEN** 旧判断不得直接用于提交新文字；即使已经进入 Final 等待也适用。新有效 Jev 结果要求更长等待时按新目标继续等，但不延长原最长连续静音上限（D-080）

#### Scenario: Deadline without semantic result
- **WHEN** 连续静音达到最长等待而 Jev 未返回或无法确认
- **THEN** 系统在用户未续说且有非空转写时提交已有文字，不继续等待 Jev；不得在兜底上限后追加 Final 等待

### Requirement: Single turn authority
自建模式 MUST 复用现有用户聚合器，保证一次用户轮次最多触发一次最终提交；厂商端点不得独立触发第二次 LLM。

#### Scenario: Partial at commit
- **WHEN** 轮次可结束但转写只有 Partial
- **THEN** 系统短暂等待 Final；到期或达到最长等待上限时，使用最新非空 Partial；等待期间用户续说则撤销结束候选。等待时长使用独立配置值；示例数值须经校准后作为上线默认值

### Requirement: Configurable final transcript wait
系统 MUST 支持独立配置 Final 等待时长。该等待 MUST 仅在轮次策略已允许结束且仅有 Partial 时开始，MUST NOT 突破最长连续静音兜底上限。

#### Scenario: Final arrives within configured wait
- **WHEN** 有效候选在配置窗口内收到 Final
- **THEN** 系统使用最终转写提交，不额外等满窗口，仍遵守最短静音及续说撤销规则

#### Scenario: Final wait expires first
- **WHEN** 配置窗口先于最长静音上限到期且仅有 Partial
- **THEN** 当前转写版本仍满足有效轮次结束条件时，系统采用当时最新非空 Partial 提交；若文字已修订，新有效 Jev 目标要求更长等待则遵守新目标，旧 Final 窗口不得绕过它。缺少新有效结果时走原最长静音保护（D-080）

#### Scenario: Maximum silence expires first
- **WHEN** 最长静音上限先于配置窗口到期
- **THEN** 系统立即采用已有非空转写提交，不追加等待

### Requirement: Optional priority echo rules
高级规则 MUST 使用停顿前实际连续数字/字母片段，长度可变，MUST NOT 以固定单元数量作为触发条件或新增位数配置。高级规则 MUST 可开关，开启且命中时 MUST 优先于 Jev 语义路径。系统 MUST 以自定义 word 单元计算速度，英文每个单词为一个单元，中文每个汉字为一个单元，数字每位为一个单元；hello 为一个单元、你好为两个单元、1234 为四个单元。计数规则 MUST NOT 自动扩大跟读匹配范围，不使用 ASR 返回的 token 数代替。

#### Scenario: Slow variable-length sequence pauses
- **WHEN** 用户念出一段实际长度为 N 的连续目标单元，可靠时间戳计算的 WPM 低于配置阈值，且随后出现候选停顿
- **THEN** 系统按已确认策略触发指定片段跟读，不因累计达到某个固定数量就直接播放

#### Scenario: User continues during echo playback
- **WHEN** 跟读正在播放且用户继续说话
- **THEN** 系统继续接收音频和转写，不因该续说取消正在播放的跟读；该特例不得自动应用到普通 LLM 回复

#### Scenario: Repeated partial update
- **WHEN** 同一片段由多个 Partial/Final 事件重复呈现
- **THEN** 系统不得重复跟读该片段；不同位置相同内容不得仅因字符串相同被错误去重

### Requirement: Advanced rule configuration and diagnostics
系统 MUST 提供上线前维护高级跟读规则词表、WPM 阈值及独立跟读停顿时长的配置能力，并在对话中展示规则评估的实际片段 WPM 与判断结果。上线后 MAY 隐藏普通用户入口；工程沿用现有角色权限并核对兼容性。

#### Scenario: Explain speed evaluation
- **WHEN** 系统对一个转写片段评估低速条件
- **THEN** 记录该片段的业务单元数、可靠 ASR 起止时间、时长、实际 WPM 及阈值；时间证据不足时标记无法计算，不得伪造数值

#### Scenario: Account for pause elapsed
- **WHEN** VAD 已确认候选停顿且高级规则要求更长静音
- **THEN** 已经过的静音计入跟读停顿，只等待剩余部分，不重复叠加完整停顿时长

### Requirement: Assistant keyword rule condition
高级跟读规则 MUST 以最近一轮普通机器人回复的整段生成文本匹配关键词，任意一个关键词命中即开启规则评估。关键词 MUST 为必需门槛，不提供单独关闭该门槛的开关；规则整体仍可开关。关键词条件 MUST NOT 单独触发跟读播放，必须同时满足词表、低于 WPM 阈值和停顿阈值，并在记录中呈现匹配证据。

#### Scenario: Explain assistant keyword match
- **WHEN** 系统评估启用了机器人关键词条件的跟读规则
- **THEN** 系统展示该条件是否匹配以及对应的机器人文本证据；匹配不代表用户已经完成输入

### Requirement: Stable assistant keyword context
关键词 MUST 仅匹配最近一轮普通机器人回复。用户 ASR 分块、Partial/Final 更新、用户 TD 分段和规则跟读 MUST NOT 刷新此关键词上下文；新的普通机器人回复才更新。该上下文专用于关键词策略，不隐式修改全部 LLM 或厂商上下文契约。

#### Scenario: User input is split after one assistant prompt
- **WHEN** 机器人提示采集编号后，用户输入被 ASR/TD 分成多个片段
- **THEN** 这些片段的规则判断继续使用该提示，不因用户分段丢失关键词条件

#### Scenario: Echo does not replace collection prompt
- **WHEN** 系统跟读一个数字/字母片段
- **THEN** 跟读不覆盖最近普通回复的关键词上下文，后续用户片段仍按原提示判断

### Requirement: Jev configuration prototype
配置界面 MUST 提供独立的 Jev 配置页面，覆盖连接、判断指令、枚举及请求预览，并可从语义 TD 设置进入/返回。Jev 判断指令 MUST 与普通回复 LLM Prompt 区分。

#### Scenario: Preview request without secret
- **WHEN** 用户在原型中编辑问题和示例对话后打开请求预览
- **THEN** 页面展示对应 state/questions，不包含 API Key，不发送真实请求；校验字段不等于证明服务连通


### Requirement: Draft semantic waiting fusion preview
The prototype SHALL present configurable per-option waits and a Noul weight, calculate Choice expected waiting using the full probability distribution, blend it with Noul-derived waiting, apply global bounds and subtract elapsed silence once. Invalid probability distributions SHALL show validation feedback. Numerical defaults remain illustrative pending calibration.

#### Scenario: Weighted waiting example
- WHEN minimum=600 ms, maximum=2500 ms, Noul=0.9, Choice complete=0.8 at 700 ms and incomplete=0.2 at 1500 ms, α=0.5 and elapsed=450 ms
- THEN the preview shows TN=790 ms, TC=860 ms, target=825 ms and remaining=375 ms.

### Requirement: TD prototype language switching
The prototype SHALL offer Chinese and English UI for TD settings, Jev settings and decision records, defaulting to Chinese, without rewriting request data or user-edited values.

#### Scenario: Switch language without changing request
- WHEN the user changes Chinese to English and back
- THEN labels and help change language while prompts, option identifiers, meanings, sample transcripts and request data stay unchanged.


### Requirement: Number collection completeness configuration
The draft SHALL distinguish a configurable complete identifier length from variable-length echo segments, provide a collection timeout independent of semantic TD and a configurable timeout utterance treated as a normal assistant reply. Before reaching the complete length, the semantic TD maximum-silence submission SHALL NOT bypass the active collection protection. The collection timer SHALL restart after each user speech stop and cancel on resumed speech. After a timeout reminder, the system SHALL re-evaluate the configured keywords against that new normal reply; only a match enables subsequent number rules. Collected units SHALL persist across reminders and re-entry within the same unfinished collection until a clear operation. After a successful collection, starting a new collection SHALL clear the old value and advance the collection generation; ASR chunks, pauses and repeated keyword matches SHALL NOT alone start a new collection. Overlength reminders SHALL supersede pending echo segments that have not started; an echo already playing SHALL finish.

#### Scenario: Target length differs from echo segment size
- GIVEN a target identifier length of 16
- WHEN a user speaks a valid three-unit segment slowly and pauses
- THEN the segment may be echoed once while the full identifier remains incomplete; subsequent segments contribute without counting repeated Partial updates again.

### Requirement: Self-developed source is sole final turn authority
When self_developed is selected for any supported ASR model, ASR SHALL continue providing transcription and timestamps while self-developed TD is the sole authority allowed to commit a user turn. This extends the previous specification scope limited to provider_native/off.

#### Scenario: Provider boundary while self-developed selected
- WHEN ASR reports a provider end-of-turn event while self_developed is selected
- THEN the event SHALL NOT independently submit a second user turn to LLM; final submission remains governed by self-developed TD.

### Requirement: Transcript stability is separate from turn ownership
In self_developed mode, adapters SHALL normalize provider partials and finals with explicit source ranges. Final text SHALL NOT independently commit a user turn. The normalized current TD transcript SHALL combine committed source segments and the latest replaceable partial tail; provider turns MAY span only part of one TD user turn. Event details and implementation evidence are documented in ../../asr-event-mapping.md.

#### Scenario: Final prefix followed by partial tail
- GIVEN a finalized source segment containing 123
- WHEN the same TD candidate receives a newer partial tail 45
- THEN its current text is 12345 and its aggregate status remains Partial until the corresponding remaining range is finalized or the bounded wait expires.

#### Scenario: Independent English segments preserve word boundaries
- WHEN independent English source segments contain one and two without boundary spaces
- THEN their combined text preserves two words (one two); numeric runs and CJK remain contiguous, existing spaces remain intact, and provider subword tokens preserve their own whitespace rather than being treated as independent words.

#### Scenario: A cross-range Final has incomplete timed word coverage
- WHEN resolving a submitted range from a longer Final requires slicing, but timed words do not cover its complete text (including negation)
- THEN the range remains unresolved and cannot trigger a reconstructed response restart; the complete source text remains available as evidence. Complete word coverage permits normal range resolution without losing word boundaries.

#### Scenario: Flux interim update must reach TD
- WHEN Flux emits an Update containing a new transcript revision
- THEN the self-developed TD cache receives that revision without waiting for provider EndOfTurn; an existing on_update-only callback without a bridge does not satisfy this requirement.

#### Scenario: Late final cannot finish newer speech
- WHEN a Final for an older source range arrives after newer partial speech
- THEN only its own range is finalized and no newer tail is cleared or marked Final. A late provider endpoint cannot independently cause another LLM submission.

### Requirement: Confirmed collection revision and clear behavior
系统 MUST 区分重复转写与真实内容修订：相同范围及版本不得重复计数或跟读；ASR 对已播片段作真实内容修订时 MUST 补读更正内容。同一未完成采集的编号只有执行清空操作才重置；成功采集后，下次启动新采集时 MUST 清空旧值并切换采集代次。第一版 MUST 将局部更正请求归为清空工具调用，不做局部替换，也不先追问；普通位数询问和请求机器人重复播报不得误清空。

#### Scenario: ASR corrects played content
- **WHEN** 已播片段 123 被 ASR 修订为 124
- **THEN** 更新该范围并补读更正内容；同一修订的重复事件不再补读

#### Scenario: User requests positional correction
- **WHEN** 用户请求“把第4位改成3”
- **THEN** 调用当前会话清空编号工具，重置已收集值和计数，使旧待播任务失效，并引导用户完整重念；不局部替换

#### Scenario: Reminder preserves collection
- **WHEN** 未满位提醒完成且新的普通机器人回复再次命中关键词
- **THEN** 恢复同一未完成采集的规则评估并保留原编号；该场景不属于成功后启动新采集

### Requirement: Strict local identifier routing
机器人关键词门槛有效时，只有当前待判定输入整体由有效编号单元与允许的格式分隔符组成，才 MAY 进入本地收集/跟读路径。本地 MUST 对完整输入做词表与格式校验，MUST NOT 仅因包含一个数字子串就通过。正则/词表只判断格式，不承担一般否定、更正或混合意图理解；MUST NOT 通过不断追加更正句式正则替代普通对话理解。片段仍为变长，不新增固定最低位数。

包含前缀、语气词、提问或其他普通表达的输入 MUST 整体进入现有普通语义TD（Jev）及对话LLM路径，MUST NOT 先提取其中数字、累加或排队跟读。混合表达及控制请求 MUST NOT 被未满位收集保护无限阻塞。只有Jev判断不修改编号；LLM对混合表达通过受控工具提交或清空编号。

#### Scenario: Pure identifier stays local
- **GIVEN** 关键词和编号规则有效
- **WHEN** 当前输入为12345且整体命中编号词表/格式
- **THEN** 本地收集；仅在可靠时间、低速、停顿及去重条件满足时跟读，不为纯编号额外调用提交编号工具

#### Scenario: Prefixed identifier uses conversation path
- **WHEN** 用户说“我的号码是123”或“嗯……我的号码是12345”
- **THEN** 整句走普通语义TD及对话LLM；在工具成功前不提取追加其中数字、不本地跟读

#### Scenario: Mixed control request
- **WHEN** 用户说“不是123，是124”或“把第4位改成3”
- **THEN** 整句交给对话LLM；按已确认更正规则调用清空工具，成功后要求完整重念；不收集123124或43，不直接替换为124

#### Scenario: Two adjacent identifier units
- **WHEN** 用户独立念出12，两位均命中词表且整体为编号输入
- **THEN** 可进入本地路径；仍需全部跟读条件，不因达到2位立即播放，独立单单元编号仍可成为候选

#### Scenario: Filler inside input
- **WHEN** 同一待判定输入为“123，嗯，45”
- **THEN** 走普通对话路径，不以本地抽取两个数字子串的方式提前累加

### Requirement: Controlled identifier tools for mixed input
对话LLM识别正常提供编号时 MUST 调用受控提交编号工具；识别主动更正时 MUST 调用清空编号工具。两工具与纯编号本地路径 MUST 共用会话编号状态、词表规范化、范围/版本去重及采集代次；MUST NOT 维护互不一致的两份编号。系统 MUST 验证工具参数确实来自当前有效输入及允许词表，不得因LLM生成数字就无条件写入。参数非法、已失效或工具失败时 MUST 保持原状态并返回失败；LLM不得声称提交/清空成功。

#### Scenario: LLM submits normal prefixed identifier
- **WHEN** 对话LLM从“我的号码是123”识别出用户提供编号并调用提交工具
- **THEN** 系统核验当前输入范围、版本、采集代次和编号内容，成功后更新统一编号及位数并返回结果；重复调用不得重复计数，不能只口头确认而不执行工具

#### Scenario: Clear on contrastive correction
- **WHEN** 对话LLM识别“不是123，是124”为更正并调用清空工具
- **THEN** 清空编号与计数，使旧代次待播和在途写入任务失效；按已确认播放表停止旧跟读，成功后才回复需完整重念

#### Scenario: Stale or failed tool call
- **WHEN** 工具来源已过期、与有效转写不符、重复调用或执行失败
- **THEN** 不新增重复/无依据数字，不误清空新代次；返回准确状态，不伪造成功

#### Scenario: Partial routing changes
- **WHEN** 同一范围Partial先像纯编号，后修订为带前缀/提问/更正的混合表达
- **THEN** 当前范围重新分流，撤销失效的待收集/待播任务；已处理范围不能再被工具重复计数。已经实际播放的内容保留事实，不能声称已撤回；仍按既有Partial及有界Final等待规则运行，不承诺预知未来语音

### Requirement: New collection after success
系统 MUST 在上一轮成功采集后，下一次真正启动新采集时清空旧编号、复位计数并切换代次。提醒、停顿和ASR分包 MUST NOT 单独触发新采集或清空。

#### Scenario: Start another collection after success
- **GIVEN** 上次采集已成功且保存旧编号
- **WHEN** 业务启动下一次新采集
- **THEN** 新采集从空值与0计数开始，旧代次事件不得回写新状态；不因Partial临时达到目标位数就伪报成功

#### Scenario: Continue an unfinished collection
- **WHEN** 当前采集未成功，超时提醒后用户继续提供编号
- **THEN** 保留此前有效值并累加，不误触发成功后新采集清空

### Requirement: Identifier followed by a question
系统 MUST 区分已独立处理的纯编号输入与同一候选中的混合句。先前有效纯编号已独立触发跟读后，后续提问不得重复收集该编号；同一输入“123，接下来还要几位”整体按混合路径处理，不再预先本地提取123。普通短语one moment MUST NOT 因one在词表内而收集为1。

#### Scenario: Question after separately handled identifier
- **GIVEN** 先前纯编号123已独立满足条件并实际跟读
- **WHEN** 用户随后问“接下来还要几位”
- **THEN** 基于统一编号状态正常回答，不重复收集或跟读123

#### Scenario: Identifier and question in one candidate
- **WHEN** 同一待判定输入为“123，接下来还要几位”
- **THEN** 整句走普通语义TD及对话LLM；正常提供编号需经提交工具，不先本地累加/跟读；本场景替代D-038的旧混合句直接跟读解释

#### Scenario: Ordinary phrase containing a number word
- **WHEN** 用户说普通短语one moment
- **THEN** 该句走普通路径，不收集为编号1，不触发数字跟读


### Requirement: Confirmed playback arbitration
系统 MUST 沿用用户填写的playback-decisions：满位普通回答已准备时跳过尚未播放的末段跟读（P03=B）；上一段补读优先于新一段（P04）；清空成功停止旧编号跟读（P05）；旧采集的临时合成结果失效（P06）；普通回复被用户打断时取消旧回答及未播旧跟读（P07）；一次持续沉默只播一次未满位提醒，之后沿用现有空闲逻辑（P08）；同范围多个未播修订合并成最新有效版本（P10）。

#### Scenario: Client-confirmed echo start
- **WHEN** 判定跟读是否已经开始
- **THEN** 采用客户端实际开播确认为证据（P11）；已发送但尚无回执标记为开播未知，不能把缺回执当成肯定未播，不能伪造播放事实

#### Scenario: Playback receipt delivery or stop confirmation stalls
- **WHEN** a renderer receipt request remains pending or a requested stop cannot be confirmed
- **THEN** the call fails explicitly within a bounded confirmation deadline, closing cancels pending receipt work, and failure telemetry cannot block media cleanup. A missing receipt does not prove a stop or authorize a new response to overlap the old task; actual accepted facts and unknown outcomes remain in history.

#### Scenario: Clear overrides ordinary echo continuation
- **WHEN** 用户更正并且清空工具成功，旧编号跟读仍在播放
- **THEN** 停止旧编号跟读并使旧待播/在途任务失效；这是明确清空的特例，普通续说仍不取消正在播放的有效跟读


### Requirement: Controlled response restart on final after partial submission
同一音频范围的Partial已提交且对应回答仍属当前轮次时，系统 MUST 在首个有效Final到达后停止对应旧回答的生成/播放，更新有效上下文，并用Final重新请求。MUST NOT 判断是否实质改义；相同文本、同义或格式变化均适用（D-049替代D-043的语义门槛）。系统 MUST 保留原提交、已播事实、来源修订、取消及重答原因；不得把重答计作第二个用户轮次。未提交的Partial只更新转写，不额外生成回复。

#### Scenario: Valid final after submitted partial
- **GIVEN** 当前用户轮次的Partial已提交并开始回答
- **WHEN** 同一来源范围的首个有效Final到达
- **THEN** 取消对应旧生成/播放和残留输出，更新有效上下文并以Final重新请求；文字相同也重答，不发语义比较请求

#### Scenario: Final before submission
- **WHEN** 有效Final在TD提交前到达
- **THEN** 更新候选转写，仍服从TD唯一提交权，不启动修订重答

#### Scenario: Duplicate or stale final revision
- **WHEN** 已处理Final重复或格式化重发，或旧轮次Final在新轮次已开始后到达
- **THEN** 不重复重答、不打断新轮次，旧输出不得进入新回答；已执行工具副作用不得因重答再次执行

### Requirement: Uniform Jev session request budget
正式自建TD MUST 每会话统一最多请求Jev100次，失败尝试计入预算。达到上限 MUST 不再请求Jev，仍按已确认最长连续静音保护处理，不因额度耗尽新增提交或绕过续说/来源验证。此规则不授权真实付费测试。

#### Scenario: Session exhausts the fixed budget
- **GIVEN** 同一会话已发起100次Jev请求
- **WHEN** 后续有效候选转写发生变化
- **THEN** 不发起第101次请求，并由仍有效的最长等待保护处理

### Requirement: Bounded failure for unavailable ASR source evidence

依据：D-061。

ASR来源身份/音频范围缺口 MUST 明确保留，MUST NOT 被无关正常帧或重连掩盖。同一轮在既有最长等待截止前取得可证明的恢复可继续；达到截止仍缺证据 MUST 以明确ASR证据错误结束当前通话并取消生成/播放、保留原转写与失败原因，MUST NOT 提交不完整用户消息、执行工具、猜来源或无限挂起。不新增页面控件/时限参数，不授权收费测试。

#### Scenario: Missing source evidence reaches maximum silence
- **GIVEN** 当前停顿候选仍有未恢复的来源/范围缺口
- **WHEN** 达到当前既有最长连续静音截止，且没有新开口/待分析音频阻止截止
- **THEN** 系统记录可诊断的ASR证据错误，结束本次通话并取消生成/播放；不新增用户提交或工具副作用，原始转写/缺失原因保留

#### Scenario: Proven recovery before the maximum
- **GIVEN** 当前候选存在来源/范围缺口
- **WHEN** 同来源或同SDK快照范围的真实证据在最长等待前恢复
- **THEN** 正常重新计算候选；无关新来源、下一轮或重连不能冒充恢复

### Requirement: Evidence-bounded playback timing

自建TD历史MUST使用实际播放任务及有效时钟关联计算playback/E2E延迟范围，保存误差边界和证据来源。MUST NOT把HTTP收件时间或假设RTT上下行各半当实际播放时间。旧历史、缺锚、失效时钟或无法关联来源时MUST明确缺失，不填0或回算旧值。D-073只批准该处指标范围展示。

#### Scenario: Correlated task render
- **WHEN** 已认证会话的实际任务开播坐标与有效时钟证据可对应
- **THEN** 历史显示可追溯的延迟上下界及误差/来源，不把区间中点伪装成精确值

#### Scenario: Uncorrelated or expired timing evidence
- **WHEN** 缺少有效关联、时钟重建、锚过期或证据相互矛盾
- **THEN** 相应跨钟指标保持缺失并说明原因，实际任务播放/停止证据仍保留
