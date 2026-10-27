# Decision Log

### D-037：成功采集后，下一次新采集清空旧编号
- Status: Confirmed
- Date: 2026-10-20
- Source thread/message: 当前Codex聊天，用户带12条Response annotations的消息，Annotation 9（编号生命周期），请求以TDD+SDD对齐自测范围。
- Confirmation quote: “如果上一次成功收集，那么就下次再进入的时候应该清空。这个是很明确的吧。”
- Decision: 补充D-028：同一未完成采集跨提醒仍保留；上次成功采集后，下一次真正启动新的采集时执行清空并换代。ASR分块、停顿或同一上下文重复匹配不能冒充新采集。不能只因Partial临时达到位数就伪报成功。
- Updated artifacts: 当前voice-pipeline Delta、design、design-appendix、tasks及self-test-plan；原型/实现仍待同步，不标记验收。

### D-038：有效编号后接位数提问，先跟读再回答
- Status: Superseded in part by D-040
- Date: 2026-10-20
- Source thread/message: 当前Codex聊天，同一12条Response annotations消息，Annotation 4（本地数字提取与控制句）。
- Confirmation quote: “另外，123，接下来还要几位。这个123肯定要先跟读。不过‘不是123，是124’这个case确实没考虑过，你怎么想的？”
- Decision: 有效123满足既有跟读条件时，先跟读该编号片段，再回答后续位数问题。普通问题不应使前面的有效编号丢失；仍遵守可靠时间、低速、停顿与去重，不把标点当作真实停顿。否定更正混合句未由此确认，列Q-038。
- Updated artifacts: voice-pipeline Delta、design-appendix、tasks、playback-decisions及self-test-plan；未冻结新播放建议。

### D-039：普通短语one moment不作为连续编号输入
- Status: Confirmed
- Date: 2026-10-20
- Source thread/message: 当前Codex聊天，同一12条Response annotations消息，Annotation 4对评审例子的纠正。
- Confirmation quote: “one moment那个你说的不对，规则是连续出现数字，这个one moment也不是连续数字啊。”
- Decision: 撤回评审中one moment的误匹配例子，明确它作为普通短语不收集为1。不由此推断所有独立单单元编号均被禁用，也不新增固定最小位数；独立念号与普通短语须分别测试。
- Updated artifacts: voice-pipeline Delta、design-appendix、tasks及self-test-plan；不宣称本地解析已实现。

### D-001：优先云端 Jev 的方案方向
- Status: Confirmed
- Date: 2026-10-20
- Source thread/message: 本聊天用户消息，以“优先验证Jev，暂不部署本地语义+声学模型。”开头；完整确认摘录见 source-message.md
- Confirmation quote: “优先验证Jev，暂不部署本地语义+声学模型。”
- Decision: 优先验证本地 Silero VAD 与云端 Jev 组合，保留上一轮机器人上下文和本轮转写，续说撤销结束判断，配置最短与最长等待。
- Consequences: 仅确认方向，不代表批准未定参数、失败行为、外部付费调用、正式开发或验收。
- Updated artifacts: proposal.md、design.md、specs/voice-pipeline/spec.md、tasks.md

### D-002：最长等待到期提交已有文字
- Status: Confirmed
- Date: 2026-10-20
- Source question: Q-001
- Source thread/message: 本聊天异步问题回复 call_1953575a8518474eaeaccf5bc17c81b2 第 0 项；source-message.md Follow-up confirmation
- Confirmation quote: “如果是的话，那么就提交已有转写”
- Decision: 问题中的最长等待就是用户提出的兜底最长等待；连续停说达到该上限，且用户未续说时，提交已有转写，不继续等待 Jev。没有文字时的行为仍待详细策略确认，不发送空白用户消息。
- Updated artifacts: design.md、specs/voice-pipeline/spec.md、tasks.md

### D-003：短等 Final，超时使用最新 Partial
- Status: Confirmed
- Date: 2026-10-20
- Source question: Q-002
- Source thread/message: 本聊天异步问题回复 call_1953575a8518474eaeaccf5bc17c81b2 第 1 项；source-message.md Follow-up confirmation
- Confirmation quote: “短暂等待 Final，超时提交最新 Partial（推荐：平衡完整性和延迟）”
- Decision: 语义策略允许结束时，若仅有 Partial，短暂等待 Final；到期采用最新 Partial。为遵守 D-002 的硬性上限，不在最长等待到期后额外启动 Final 等待。具体 Final 等待时长仍未确认。
- Updated artifacts: design.md、specs/voice-pipeline/spec.md、tasks.md

### D-004：Final 等待时长可配置
- Status: Confirmed
- Date: 2026-10-20
- Source thread/message: 本聊天用户消息“这个短暂等待final，短暂等待时间需要支持配置”；source-message.md Configurable Final wait
- Confirmation quote: “这个短暂等待final，短暂等待时间需要支持配置”
- Decision: Final 等待窗口必须支持独立配置，并仍受 D-002 最长连续静音上限约束；具体默认值、范围、配置入口与生效范围未确认，不假定新增页面。
- Updated artifacts: design.md、specs/voice-pipeline/spec.md、tasks.md

### D-005：补充 VAD 参数能力目录
- Status: Confirmed
- Date: 2026-10-20
- Source thread/message: 本聊天用户对 design.md 第 34 行的选中评论，source-message.md VAD parameter documentation
- Confirmation quote: “VAD自身的配置参数，也需要补充。除了短停顿检测时间（可配置的），还有哪些参数能配呢？Silero VAD”
- Decision: 设计文档列出当前封装的短停顿、开口确认、人声概率、最低音量四项及音频约束；仅短停顿可配置是明确产品要求，其他项的暴露方式与默认值不标记为已确认。
- Updated artifacts: design.md、tasks.md

### D-006：高级规则优先及慢速四位停顿跟读
- Status: Confirmed
- Date: 2026-10-20
- Source thread/message: 本聊天高级规则请求及最新 annotation 回复，source-message.md Advanced rule confirmations
- Confirmation quote: “规则可以开关，一旦开启，就默认优先级比送给Jev高。”“只有用户在慢速念完四位并停顿时候跟读。”
- Decision: 添加可开关的高优先级规则，按自定义 WPM 统计每个数字/字母单元，1234 算 4 word；慢速四位后停顿才跟读，同一片段防重复；跟读播放期间允许用户同时说，不打断该跟读。
- Consequences: 仅确认上述行为，不确认普通回复关闭打断；同音词规则、阈值、分组及回声保护仍需确认/验证。
- Updated artifacts: design.md、specs/voice-pipeline/spec.md、tasks.md

### D-007：跟读触发位数可配置
- Status: Superseded
- Date: 2026-10-20
- Source thread/message: 本聊天对分组数量的最新修正，source-message.md Configurable echo length
- Confirmation quote: “不过不一定是慢速四位，可能是慢速三位/慢速五位”
- Decision: D-006 中固定四位修改为可配置 N 位，至少覆盖 3、4、5；对应速度公式使用 N 个业务单元，仍须低速及停顿才触发。默认值和完整允许范围未确认。
- Updated artifacts: design.md、specs/voice-pipeline/spec.md

### D-008：变长跟读，不配置位数
- Status: Confirmed
- Date: 2026-10-20
- Source thread/message: 本聊天最新用户修正；source-message.md Variable echo length
- Confirmation quote: “不一定是固定的啊，不需要配置。”
- Decision: 撤销 D-007 的位数可配置解释。以用户停顿前实际连续数字/字母片段作为候选，长度可变；WPM 的 N 取实际单元数，不存在固定或配置位数门槛。仍要求慢速及停顿、去重和跟读中允许用户续说。
- Updated artifacts: design.md、specs/voice-pipeline/spec.md、decisions/open-questions.md

### D-009：按语言定义 WPM 单元
- Status: Confirmed
- Date: 2026-10-20
- Source thread/message: 本聊天 design.md 第 32 行选中“英文字母”的用户评论；source-message.md WPM language units
- Confirmation quote: “就是英文单词算一个word，但是比如中文这种，一个字就是一个word”
- Decision: 修正此前每个英文字母计一个 word 的概括：英文按单词、中文按汉字计数，保留此前确认的数字逐位计数。该决定定义速度统计，不把所有英文单词扩展为跟读目标；逐字母拼读和其他语言仍待明确。
- Updated artifacts: design.md、specs/voice-pipeline/spec.md

### D-010：配置能力与原型页面建议先写草案
- Status: Confirmed
- Date: 2026-10-20
- Source thread/message: 本聊天用户确认先改设计草案，source-message.md Configuration page and prototype proposal
- Confirmation quote: “对，你先改一下设计草案。然后我们再说原型的事情。你先在设计草案里面写一下建议原型页面怎么设计”
- Decision: 草案采用一个高级规则配置页分区维护词表、WPM 阈值和跟读停顿，对话内统计片段 WPM；上线前可配置，上线后可以不暴露普通入口。此轮只写建议原型方案，不创建或冻结 HTML 原型，不开发页面。
- Consequences: 页面位置、保存生效、权限、默认值和统计留存细节仍为待确认建议；ASR start/end 与 VAD 停顿时间分别负责语速和静音计算。
- Updated artifacts: design.md、specs/voice-pipeline/spec.md、tasks.md

### D-011：机器人关键词可作为跟读条件
- Status: Confirmed
- Date: 2026-10-20
- Source thread/message: 本聊天最新用户追加关键词条件，source-message.md Assistant keyword condition
- Confirmation quote: “命中条件也可以有‘机器人说了什么关键字’”
- Decision: 高级规则支持机器人输出关键词条件，作为后续跟读的场景依据。关键词列表可维护，配置页建议与判断记录需呈现此条件。
- Consequences: 机器人文本取实际播放还是完整生成、匹配窗口、关键词组合、与其他条件的关系及重置条件尚未确认；不得仅因机器人说出关键词就立即跟读。
- Updated artifacts: design.md、specs/voice-pipeline/spec.md、decisions/open-questions.md、tasks.md

### D-012：机器人关键词只匹配最近一轮回复
- Status: Confirmed
- Date: 2026-10-20
- Source thread/message: 本聊天对“建议先只匹配机器人最近一轮回复”的 annotation 1
- Confirmation quote: “是的，只匹配最近一轮回复，但是如果轮次断错了怎么办？”
- Decision: 关键词只匹配最近一轮机器人回复，不检索更早历史；错误轮次切分后的上下文保持、普通回复与跟读输出的区分为待确认方案。
- Updated artifacts: design.md、decisions/open-questions.md

### D-013：分段与跟读不刷新关键词上下文
- Status: Confirmed
- Date: 2026-10-20
- Source thread/message: 本聊天紧接“用户输入被切成几段与机器人最近一次提示分开管理”说明后的用户确认，source-message.md Context snapshot confirmation
- Confirmation quote: “对的，就是这个意思”
- Decision: 用户 ASR/TD 分段及规则跟读均不刷新关键词上下文；同一提示后的各输入片段沿用最近普通机器人回复，只有新的普通机器人回复更新。跟读明确区别于普通回复。
- Consequences: 该保护不等于修复误切分已触发的错误普通回复；快照更新的生成/播放边界和取消恢复策略仍待确认。
- Updated artifacts: design.md、specs/voice-pipeline/spec.md、decisions/open-questions.md

### D-014：制作沿用线上样式的独立原型
- Status: Confirmed
- Date: 2026-10-20
- Source thread/message: 本聊天原型请求及登录确认，source-message.md Prototype creation authorization
- Confirmation quote: “一定要参考现在线上页面样式。不能动现在线上页面样式”
- Decision: 在 Change prototypes/ 制作单文件交互原型，参考登录后的线上页面与当前 CSS，不编辑正式 frontend 或部署。原型用于后续评审，不代表规格和视觉已确认。
- Updated artifacts: prototypes/index.html、prototypes/README.md、verification/ui-checklist.md、design.md

### D-015：独立 Jev 配置页及普通提示样式
- Status: Confirmed
- Date: 2026-10-20
- Source thread/message: 本聊天 Jev page prototype 请求与 Browser comment 1，source-message.md Jev page prototype
- Confirmation quote: “那配置原型你补一下？这个Jev 配置感觉可以单独一个页面。”
- Decision: 原型补独立 Jev 页面，从语义设置进入；计时说明去除按钮外观。具体字段结构为待评审设计，不自动确认参数或真实 API 调用授权。
- Updated artifacts: prototypes/index.html、prototypes/README.md、design.md、verification/ui-checklist.md


### D-016：融合等待公式与中文页面切换
- Status: Confirmed（先用于原型，数值参数未冻结）
- Date: 2026-10-20
- Source thread/message: 本会话紧接“对，那你看看有没有什么合理的公式设计这个”后的用户确认消息。
- Confirmation quote: “可以，按照这个先来一版。然后整个TD页面模块，都需要加一个中文页面的切换，这么多英文我有点看不懂了。”
- Decision: 原型采用 Noul 等待与 Choice 全分布期望等待的线性融合，最后输出等待时长；明显冲突时取较长等待。提供中文 / English 切换，默认中文，覆盖 TD、Jev 配置、判断记录。切换不修改用户填写的指令、选项标识、含义、转写或请求内容。
- Parameters: α=0.5、冲突门槛=0.8 及所有等待时间均为原型示例，实测校准移至工程任务，原 Q-003 已拆除；自定义选项参与期望等待，冲突分组示例仅识别 complete / incomplete / holding_floor。
- Closure: Q-006 的融合方向迁入本决定；不代表参数、真实接口或原型验收已确认。

### D-017：编号完整长度与独立保护配置
- Status: Confirmed
- Date: 2026-10-20
- Source thread/message: 本聊天“另外，priority rules里面应该针对编号设置一个位数”请求。
- Confirmation quote: “即如果没有收集到指定的位数就一直等待，然后这个等待也有个保护时间，跟semanticTD可以不是一个时间。这样逻辑会更完整。然后针对这种情况超时的话，应该能配置一个默认话术……然后这个也算一个机器人回复。”
- Decision: 增加完整编号目标位数、独立收集等待保护和超时话术；提醒属于普通机器人回复，区别于片段跟读。未满位不能被普通 semantic TD 最长等待提前提交；独立保护仍必须保证退出等待。
- Consequences: 片段三位或五位仍由实际停顿决定；目标位数约束完整编号，不恢复固定跟读片段长度。计时起点、提醒后状态和满位/超位行为见 Q-007，尚未确认。

### D-018：收集静音计时与提醒后关键词重判
- Status: Confirmed
- Date: 2026-10-20
- Source thread/message: 本轮两个异步问题的用户逐项答复。
- Confirmation quote: “每次用户停下后重新计时（推荐，避免用户持续念号时超时）”；“看这个机器人回复里面是否包含关键词，而不是写死是否继续收集。”
- Decision: 每次用户停止说话开启新的收集静音等待；续说撤销本次等待，下次停下重新起算。超时提醒作为新的普通回复，重新匹配其关键词；命中才启用后续规则，不命中回到普通 semantic TD。关键词、有效词表、低于 WPM 阈值、可靠时间戳、停顿和去重条件全部满足才跟读。
- Consequences: 不因提醒是系统生成就绕过关键词入口；已收内容是否跨提醒保留、满位 / 超位处理归 Q-008。

### D-019：线上页面对齐与全部 ASR 自建来源入口
- Status: Confirmed
- Date: 2026-10-20
- Source thread/message: 本聊天“sessions页面/shate页面，不符合线上样式”请求。
- Confirmation quote: “ASR配置项里面Turn detection source=Self-develped的时候，才可以展示这个advanced的配置。然后，所有的ASR都要支持配置self-developed Turn detection source。”
- Decision: Sessions/Share 参考当前线上页面布局。所有当前 Catalog ASR/model 均须增加 self_developed 选项；仅选择该来源时展示 Advanced 的自建 TD 区域与 Jev 入口。原有 Advanced 通用 fallback 保留。拼写统一 Self-developed。
- Scope: 本轮更新设计、Delta 和原型，不修改正式 frontend/src、后端 Catalog 或生产配置；原生/off 既有能力限制继续适用。
- Updated artifacts: design.md、specs/bot-config/spec.md、specs/voice-pipeline/spec.md、prototypes/index.html、verification/ui-checklist.md

### D-020：会话详情逐 Turn 记录与多轮示例
- Status: Confirmed
- Date: 2026-10-20
- Source thread/message: 本轮 Browser comment 1，选中 aside#td-history。
- Confirmation quote: “详情里面，不应该每一个turn都有一次记录吗？这里面为什么只有一条？然后你多造几条数据，原来正常的怎么展示”
- Decision: 详情按用户 Turn 关联对话、普通机器人回复、原有延迟指标与 TD 记录；同一 Turn 内可展开多次候选停顿判断，不能只展示一条会话级结果。补多会话、多轮正常与兜底 fixture。历史未采集自建 TD 的会话显示未启用，不伪造 Jev 结果。
- Scope: 仅设计与原型 fixture，不接真实历史 API，不重定义 backend turn_count。编号收集分组标为尚未提交 LLM，跟读片段不冒充独立 LLM 轮次。

### D-021：预合成跟读音频与可调播报空隙
- Status: Confirmed（50ms 为建议默认，音质待测）
- Date: 2026-10-20
- Source thread/message: 本聊天预合成缓存请求及两个异步问题答复。
- Confirmation quote: “每个数字单独合成，到时候命中哪个数字就直接从缓存里面找”；“内容词表页面下方增加一个合成对应文本音频并试听的按钮”；“数字间播报空隙……比如50ms，然后支持调节”；“每次pulish的时候检查。然后这部分缓存应该永久保存，前端提示。”；“阻止发布，先补齐缓存（推荐，发布动作不自动产生 TTS 费用）”。
- Decision: 当前 Bot TTS 配置预合成去重单元并永久保存；词表下提供合成与试听，空隙可调。每次 Publish 检查匹配和完整性，缺失 / 失配 / 失败阻止发布；发布不自动补合成。
- Scope: 本轮只设计和原型清单，不调用真实 TTS、不生成假试听、不表示已有永久存储。

### D-022：词表行内复用与批量合成
- Status: Confirmed
- Date: 2026-10-20
- Source thread/message: 本聊天“为啥不放在内容词表每一行的旁边呢”反馈。
- Confirmation quote: “左边的识别文本可以逗号隔开”；“内容词表旁边就是一个一键合成。空隙在下面可以单独配置，然后试听也是在每个行的旁边”。
- Decision: 多个识别词在一行逗号分隔，共用一个跟读文本；行内显示音频状态与试听，词表标题旁一键合成，下方单独配置间隔。去掉独立重复单元清单与整串试听区域。永久保存和Publish检查不变。

### D-023：补齐超位提醒话术
- Status: Confirmed
- Date: 2026-10-20
- Source thread/message: 本聊天“那个超过位数的话术，你没加啊”及前文超位请求。
- Confirmation quote: “超过位数的时候，应该只要稍有停顿、就有一个回复吧？这样应该有一个超位数提醒话术？”；“那个超过位数的话术，你没加啊”。
- Decision: 补独立可配置超位话术，超位短停顿后提醒，不沿用未满位超时等待。具体去重与更正边界未冻结。

### D-024：时间戳能力由工程核查
- Status: Confirmed
- Date: 2026-10-20
- Source thread/message: 本聊天“ASR缺少时间戳的问题，你得提前看看”请求。
- Confirmation quote: “这个不是我要确认的，是你要确认的”；“转写修订和跟读队列重叠的处理，刚刚我们应该讨论过了吧？”
- Decision: 逐家核对官方时间字段和现有适配层，技术缺口放tasks；重新梳理已讨论的修订/去重/续说行为，不把未明确的具体补播策略伪标确认。

### D-025：简版核心正文与中文细则附录
- Status: Confirmed
- Date: 2026-10-20
- Source thread/message: 本轮中文附录请求及“核心设计还是要保持简短”补充。
- Confirmation quote: “逻辑流程图+原型示意图+逻辑解释/按钮或者字段解释写的清楚但不啰嗦”；“核心设计主要是我看和一些关键设计理念和决策……太长了我看不过来”。
- Decision: design.md仅保留核心图、分工/决策和边界；末尾链接详细中文design-appendix.md，历史演进移至design-history.md。保留原文以追溯，不改正式产品实现。

## 2026-10-20 问题清理记录（非新增行为确认）
用户要求：“那你更新一下这些待确认问题列表。看看现在还有吗？”
原Q-003已拆除：已确定内容引用D-002/003/004/019；校准、兼容性和付费测试准备迁入tasks。其余复合项拆成具体选择，详见question-review-20261020.md。不代表用户接受任何推荐答案。

### D-026：已经跟读后，ASR自己改字，要不要再读？
- Status: Confirmed
- Date: 2026-10-20
- Source question: Q-004
- Source thread/message: 用户编辑decisions/confirmed-questions-20261020.md中Q-004，并在本聊天确认“待确认列表我已经都confirm了”。
- Confirmation quote: “要补读。”
- Decision: B。ASR自动改字后，需要补读更正内容。
- Updated artifacts: design.md、appendices/behavior-details.md、appendices/asr-event-mapping.md、appendices/echo-audio-cache.md、Delta Specs、tasks.md。仅文档同步，不标记业务/原型已验收。

### D-027：关键词按机器人生成的内容，还是用户实际听到的内容匹配？
- Status: Confirmed
- Date: 2026-10-20
- Source question: Q-005
- Source thread/message: 用户编辑decisions/confirmed-questions-20261020.md中Q-005，并在本聊天确认“待确认列表我已经都confirm了”。
- Confirmation quote: “按照整段生成内容匹配就行，因为后面还有一层条件判断。”
- Decision: B。按机器人整段生成内容匹配，不依赖实际播放进度。
- Updated artifacts: design.md、appendices/behavior-details.md、appendices/asr-event-mapping.md、appendices/echo-audio-cache.md、Delta Specs、tasks.md。仅文档同步，不标记业务/原型已验收。

### D-028：提醒后再次进入收集，已有编号是否保留？
- Status: Confirmed
- Date: 2026-10-20
- Source question: Q-008
- Source thread/message: 用户编辑decisions/confirmed-questions-20261020.md中Q-008，并在本聊天确认“待确认列表我已经都confirm了”。
- Confirmation quote: “选择A，只有明确收到清空操作才重置。”
- Decision: A。提醒后再次进入收集时保留已有编号，后续输入继续累加，只有明确收到清空操作才重置。
- Updated artifacts: design.md、appendices/behavior-details.md、appendices/asr-event-mapping.md、appendices/echo-audio-cache.md、Delta Specs、tasks.md。仅文档同步，不标记业务/原型已验收。

### D-029：发布后缓存意外读不到，怎么办？
- Status: Confirmed
- Date: 2026-10-20
- Source question: Q-009
- Source thread/message: 用户编辑decisions/confirmed-questions-20261020.md中Q-009，并在本聊天确认“待确认列表我已经都confirm了”。
- Confirmation quote: “B临时调用TTS补合成，但是要在之后对话记录里面留痕显示。”
- Decision: B。运行时读不到缓存时，临时调用TTS补合成后再跟读，并在后续对话记录中留痕显示。
- Updated artifacts: design.md、appendices/behavior-details.md、appendices/asr-event-mapping.md、appendices/echo-audio-cache.md、Delta Specs、tasks.md。仅文档同步，不标记业务/原型已验收。

### D-030：通话中调整机器人语速，缓存数字要不要跟着变速？
- Status: Confirmed
- Date: 2026-10-20
- Source question: Q-010
- Source thread/message: 用户编辑decisions/confirmed-questions-20261020.md中Q-010，并在本聊天确认“待确认列表我已经都confirm了”。
- Confirmation quote: “数字跟读不用变，选择A。”
- Decision: A。数字跟读保持发布时语速，普通回复使用调整后的语速。
- Updated artifacts: design.md、appendices/behavior-details.md、appendices/asr-event-mapping.md、appendices/echo-audio-cache.md、Delta Specs、tasks.md。仅文档同步，不标记业务/原型已验收。

### D-031：最后一段跟读与超位提醒同时触发，先播哪个？
- Status: Confirmed
- Date: 2026-10-20
- Source question: Q-011
- Source thread/message: 用户编辑decisions/confirmed-questions-20261020.md中Q-011，并在本聊天确认“待确认列表我已经都confirm了”。
- Confirmation quote: “选择A，让位给提醒。”
- Decision: A。待播的末段跟读让位给超位提醒，尚未开始的本段跟读不再入队；已开始的跟读仍播完，不改变用户续说不打断正在播放跟读的规则。
- Updated artifacts: design.md、appendices/behavior-details.md、appendices/asr-event-mapping.md、appendices/echo-audio-cache.md、Delta Specs、tasks.md。仅文档同步，不标记业务/原型已验收。

### D-032：第一版编号更正支持到什么程度？
- Status: Confirmed
- Date: 2026-10-20
- Source question: Q-012
- Source thread/message: 用户编辑decisions/confirmed-questions-20261020.md中Q-012，并在本聊天确认“待确认列表我已经都confirm了”。
- Confirmation quote: “不用支持把第四位改成3，这个请求就算成清空；清空工具需要相应修改。”
- Decision: B。不支持“把第4位改成3”等局部修改，此类请求直接调用清空工具清空已有编号，不执行局部替换，也不先追问；调整清空工具的说明和触发范围，覆盖此类更正请求。
- Updated artifacts: design.md、appendices/behavior-details.md、appendices/asr-event-mapping.md、appendices/echo-audio-cache.md、Delta Specs、tasks.md。仅文档同步，不标记业务/原型已验收。

### D-033：配置多个机器人关键词时，命中一个就生效吗？
- Status: Confirmed
- Date: 2026-10-20
- Source question: Q-013
- Source thread/message: 用户编辑decisions/confirmed-questions-20261020.md中Q-013，并在本聊天确认“待确认列表我已经都confirm了”。
- Confirmation quote: “命中任意一个就行。”
- Decision: A。配置多个机器人关键词时，命中任意一个即满足关键词条件，仍需通过后续条件判断。
- Updated artifacts: design.md、appendices/behavior-details.md、appendices/asr-event-mapping.md、appendices/echo-audio-cache.md、Delta Specs、tasks.md。仅文档同步，不标记业务/原型已验收。

### D-034：是否保留“不检查机器人关键词”的开关？
- Status: Confirmed
- Date: 2026-10-20
- Source question: Q-014
- Source thread/message: 用户编辑decisions/confirmed-questions-20261020.md中Q-014，并在本聊天确认“待确认列表我已经都confirm了”。
- Confirmation quote: “是啊，一定要机器人关键词触发。”
- Decision: A。编号规则始终需要机器人关键词触发，命中后仍需通过后续条件判断；去掉单独关闭关键词检查的开关，仍可关闭整套优先规则。
- Updated artifacts: design.md、appendices/behavior-details.md、appendices/asr-event-mapping.md、appendices/echo-audio-cache.md、Delta Specs、tasks.md。仅文档同步，不标记业务/原型已验收。

### D-035：带前缀表达提取连续编号片段
- Status: Superseded in part by D-040
- Date: 2026-10-20
- Source thread/message: 本聊天用户选中design-appendix.md“运行总流程”后提出前缀匹配修正。
- Confirmation quote: “所以我建议还是能够命中连续几位数字这种，不能判断用户说的是纯数字、才跟读。”
- Decision: 支持“嗯”“我的号码是”等前缀，从有效编号输入中提取连续词表片段；不要求整句纯数字。延续已有低速、停顿和时间证据条件，片段长度可变；提问/控制不因含数字误收集。前缀不参与片段WPM或跟读。
- Updated artifacts: design.md、appendices/behavior-details.md、voice-pipeline Delta Spec及tasks.md；仅文档更新，未宣称解析已实现。

### D-036：本地片段匹配与两位连续片段说明
- Status: Superseded in part by D-040
- Date: 2026-10-20
- Source thread/message: 本聊天用户指出已进入关键词窗口，随后确认两位片段并要求文档补充和一致性审阅。
- Confirmation quote: “为啥还需要Jev/LLM判断？”；“就是2位数字，就算连续片段？”；“好的。那你也补充说明一下吧。”
- Decision: 关键词窗口内直接本地词表提取，不增加前置Jev/LLM判断。两位相邻有效编号单元即构成片段，但不因达到两位立即播放；沿用既定不设最低片段位数、低速及停顿等合并条件。明确控制句式本地拦截后走普通语义/工具路径，避免误收指令数字。
- Updated artifacts: 当前核心设计、附录、Delta Spec及工程任务；历史快照仅补效力说明，保留原文。


### D-040：严格本地纯编号规则，混合表达走对话LLM工具
- Status: Confirmed
- Date: 2026-10-20
- Source thread/message: 当前Codex聊天，用户对“收紧本地规则”批注回复“我同意你这个收紧本地规则的做法。你重新表述一下你的设计调整。”；随后就提交编号工具及分工讨论后，明确要求写入文档。
- Confirmation quote: “我同意你这个收紧本地规则的做法。”；“可以。按这样的设计，明确写入更正和注意事项里面吧”
- Decision: 仅明确纯编号输入走本地词表/格式收集和既有条件跟读。带前缀、提问、更正等混合表达整体走Jev普通语义TD及现有对话LLM，不先抽数字、累加或本地跟读；不堆更正正则。正常提供编号由LLM调用受控提交编号工具，更正由LLM调用清空工具，两者共用本地编号状态与范围/版本去重。工具成功后才能确认状态变更。此为复杂表达正式路径，不只是出错补救。
- Supersedes: D-035/D-036的前缀本地抽取与本地更正句式拦截；D-038的同一混合句先本地抽取解释。已独立处理纯编号后再提问不重复收集；变长片段、关键词、WPM及停顿条件保留。
- Updated artifacts: corrections-and-cautions、design、design-appendix、voice-pipeline Delta、tasks、self-test-plan、ASR映射及交付状态；原型与业务实现仍待同步。

### D-041：播放表用户填写选择确认
- Status: Confirmed
- Date: 2026-10-20
- Source thread/message: 用户直接编辑playback-decisions.md的用户选择列；当前Codex聊天紧接P10/P11解释后明确确认整张表。
- Confirmation quote: “行，你这个列表我都确认完了，但是我记得你之前还有一些问题我没看懂。其中有一个我印象深刻的是说‘不是123，是124’这个case怎么解呢？”
- Decision: 关闭Q-037。保存用户实际选择：P03=B跳过未播末段直接回答；P04上一段始终优先；P05/P06/P07/P08/P10/P11=A。P01/P02原确认保留；P09之后受D-040混合句路由取代，不将Codex推荐当作用户选择。
- Updated artifacts: playback-decisions、voice-pipeline Delta、design-appendix、tasks、self-test-plan和open-questions；仅确认契约，不是播放功能验收。

### D-042：不是123，是124按清空完整重念
- Status: Confirmed
- Date: 2026-10-20
- Source thread/message: 当前Codex聊天，助手就“第一版也按清空后完整重念处理吗”提问后，用户明确答复，随后继续确认严格本地与LLM工具分工。
- Confirmation quote: “可以。但是实际上你怎么做的呢？”
- Decision: 关闭Q-038。该句由普通语义路径交现有对话LLM判断更正并调用清空工具；成功后要求重念完整编号，不收集123124、不直接把124替换为完整编号。本地更正正则的中间建议已被D-040替代。
- Updated artifacts: 更正与注意事项、voice-pipeline Delta、design-appendix、tasks、自测计划及open-questions。


### D-043：有效Final实质改义时停止旧回答并重答
- Status: Confirmed
- Date: 2026-10-20
- Source question: Q-039
- Source thread/message: 当前Codex聊天，用户对助手解释Q-039后批注“为什么推荐选A呢？我觉得应该选B啊”；助手随后明确停止旧回答重答及三条保护，用户紧接回复“对的”。
- Confirmation quote: “为什么推荐选A呢？我觉得应该选B啊”；“对的”
- Decision: 选择B。同一段语音的有效Final相较已提交转写发生实质意思变化时，停止对应旧回答的生成和播放，基于修订文本重答。仅标点、格式或意思不变不触发；相同修订不重复触发，旧轮次迟到结果不得打断新轮次。更新对话上下文，保留原提交、已播放事实、取消与重答原因。本规则是同一用户轮次的受控修订重答，不是厂商Final重新获得独立提交权。
- Updated artifacts: voice-pipeline Delta、design、design-appendix、更正与注意事项、self-test-plan、tasks、README、proposal、handoff及交付状态；关闭Q-039。仅文档契约确认，原型/代码/真实效果仍未实现验证，未授权付费测试。


### D-044：M0由评审Codex与用户完成，再交研发
- Status: Confirmed
- Date: 2026-10-20
- Source thread/message: 当前Codex聊天，用户在研发提示词后指出M0交接边界，随后要求整理自测范围供核对。
- Confirmation quote: “那这个M0是不是得咱俩做啊？Gate1通过之后，再给研发，比较合理”；“来吧，我这边原型和范围都确认一遍了。你先整理下，我看看自测范围就行了吧”
- Decision: M0由当前评审Codex与用户完成，用户只需简明核对自测范围；Gate 1完整通过后研发从M1开始。接受用户对已讨论原型与范围的确认陈述，不重复询问既有规则。本轮呈现自测简版，没有据此伪造具体原型文件版本/SHA对应的确认或实际功能通过；文件同步及唯一基线证据由M0核查落实。
- Updated artifacts: tasks、handoff、README、verification/self-test-scope.md及self-test-plan.md。没有开启核心实现、独立验收或付费调用。


### D-045：自测范围确认与AEC实测边界
- Status: Confirmed
- Date: 2026-10-20
- Source thread/message: 当前Codex聊天，用户查看自测范围简版后就AEC连续讨论，明确服务端先不加AEC，随后确认范围并询问Gate 1状态。
- Confirmation quote: “行，那实际做的时候没有回声消除，就现在我们的服务端先不加是吧。不会有代码问题吧”；“行，那我看这个范围差不多了，是不是代表User Gate1通过了”
- Decision: 确认verification/self-test-scope.md对应的自测范围。当前服务端不新增AEC模块；先检查浏览器实际采集设置并做软件测试，没有物理麦克风时真实外放/双讲AEC效果保留待验证，后续有设备再实测。范围确认不代表真实费用授权、功能通过或放弃Gate 2实机证据。User Gate 1仍须完成已确认规则到原型文件的同步及可追溯唯一基线，不能据本条伪造完成。
- Updated artifacts: 自测简版/细则、README、delivery-status；未改核心代码或执行真实调用。

### D-046：删除原型额外分流演示控件
- Status: Confirmed
- Date: 2026-10-21
- Source thread/message: 当前Codex聊天，用户针对127.0.0.1:8767/prototypes/index.html编号处理路径示例选择器提出删除。
- Confirmation quote: “原型里面不需要加这个啊。你这个玩意儿放到原型里面干啥啊。去掉他”
- Decision: 删除原型中的整个编号处理路径示例区域、选择器及关联脚本，不移至其他原型区域。保留文档中的分流契约，不增加真实配置项；本条不代表确认整个候选或Gate 1通过。
- Updated artifacts: prototypes/index.html、原型说明、浏览器检查与交付记录。

### D-047：原型设置只呈现产品配置
- Status: Confirmed
- Date: 2026-10-21
- Source thread/message: 当前Codex聊天，用户对播放行为及语义TD页连续批注。
- Confirmation quote: “原型是给用户看的页面”；“这部分也不需要，你写后段逻辑干啥啊”；“这一块也不需要”；“不需要”。
- Decision: 删除配置页面中的播放仲裁、Final修订重答、已耗时计算、状态等待位置说明、上下文管理及AEC验收等研发说明；不删除真实配置字段，只保留必要填写提示。后端行为契约保留在Spec与研发文档。
- Updated artifacts: 原型、说明、检查脚本及交付状态；候选仍待用户确认。

### D-048：User Gate 1确认与原型冻结
- Status: Confirmed
- Date: 2026-10-21 (America/Los_Angeles)
- Source thread/message: 当前Codex聊天；用户在D-046/D-047删除示例选择器及配置页研发说明、收到检查结果后，查看127.0.0.1:8767/prototypes/index.html的最新v0.14提出本条确认；原话可在当前聊天精确检索。
- Confirmation quote: “行，这回差不多了。那么User Gate1是不是算完成了”
- Decision: 结合已确认范围、Delta、设计、任务与D-045自测范围，确认本次清理后的v0.14原型，完成User Gate 1；研发从M1开始，遵循SDD＋TDD，开发完成先自测、再独立审核、最后User Gate 2。本确认不代表功能已实现、真实效果通过或付费调用授权。
- Frozen artifact: prototypes/index.html；唯一版本v0.14（D-047清理后）；SHA-256：`657d49b9abf71c872eeaf7f6ccc0b3dfd96b1e4dc9bcd52bb92f43b0778902b4`。
- Updated artifacts: 原型基线记录、README、tasks、handoff、自测计划与delivery-status。

### D-049：有效Final替换已提交Partial并重答，不做改义判断
- Status: Confirmed
- Date: 2026-10-21 (America/Los_Angeles)
- Source thread/message: 本次研发接手聊天；对Q-040异步问题的用户回复（request_user_input_async call_5606979fd4b84ab685fc43ab6592afb2，第0项）。
- Confirmation quote: “不用判断是否实质改义，只要收到Final，就取消掉原来的partial，用新的final请求，即可。”
- Decision: 同一来源范围、当前轮次中，Partial已提交后，首个有效Final取消对应旧生成/播放，更新有效上下文并以Final重新请求；不做含义比较，文字相同或仅格式变化也适用。重复Final去重，旧轮次不得打断新轮次；已执行工具副作用不可无条件重放，已播事实保留。未提交的Partial正常由Final替换，不额外触发回复。
- Supersedes: D-043中实质改义判定及同义/格式不重答的限制；关闭Q-040，不新增语义比较API调用。
- Updated artifacts: voice-pipeline Delta、design、development-guide、tasks、self-test-plan。冻结HTML保持原字节；其旧实质改义诊断示例不再作为运行时重答条件，以本决定及Delta为准；正式UI不得新增配置控件。
- External authorization: None；仍未授权任何真实收费测试。

### D-050：Jev每会话后台统一100次调用上限
- Status: Confirmed
- Date: 2026-10-21 (America/Los_Angeles)
- Source thread/message: 本次研发接手聊天；用户对request_user_input_async call_84734a771bf34b38988c2db61ce600da第0项的回复。
- Confirmation quote: “A：后台统一每会话100次，不增加控件（推荐）”
- Decision: 正式自建TD每会话最多100次Jev请求（失败计入已有请求预算）；达到上限不继续请求Jev，保留已确认的最长静音保护提交行为。此限额在后台统一，不在配置页增加控件。历史草稿max_calls如有其他正数，载入后规范为100，不能借旧字段绕过统一上限；新Bot无需填写隐藏工程字段。
- Updated artifacts: bot-config和voice-pipeline Delta、design、tasks、自测计划、配置模型、正式表单与回归测试。冻结HTML保持原字节，视觉基线不变。
- Closes: Q-041。
- External authorization: None；本决定不授权任何真实/付费测试。

### D-051：自建TD WebRTC下行使用带任务身份的数据通道音频
- Status: Withdrawn / not authorized for implementation
- Date: 2026-10-22 (America/Los_Angeles)
- Source thread/message: 本研发聊天，紧接A/B解释后的用户消息“先选择A吧，虽然你说的我看不懂。”
- Confirmation quote: “先选择A吧，虽然你说的我看不懂。”
- Decision: 采用Q-042方案A：仅self_developed TD的WebRTC机器人下行，以同一WebRTC连接的可靠数据通道传带任务身份的PCM，复用现有AudioWorklet任务播放器和实际渲染/停止回执；麦克风上行、ICE/信令保持现有路径。Provider-native保持原音轨。不得同时播放两套下行。页面流程保持原正式入口，不新增验收页或服务端AEC。
- Validation: 需本地正式信令/数据通道/任务音频/定向停止/清空/串行与认证回执测试；队列/带宽/弱网/断线和移动兼容分别留证。桌面通过不得代替手机或真实弱网结论。
- External authorization: None；不授权真实数据/付费API或部署。
- Closes: Q-042。

### D-052：撤回A执行批准，先核查现有音轨最小取消方案
- Status: Confirmed
- Date: 2026-10-22 (America/Los_Angeles)
- Source thread/message: 本研发聊天用户最新消息。
- Confirmation quote: “等会儿，先别直接批准 A，让研发说明现有 WebRTC 音轨为什么无法满足取消要求，以及最小改动方案能做到什么程度。 ‘要能停止旧回答’已经确定，但不意味着必须更换整条下行音频传输方式。”
- Decision: 撤回D-051的A执行批准；不更换下行音频通路，先基于锁定SDK和浏览器能力说明现有音轨取消机制、最小改动及未保证边界。用户确认后再决定是否改变媒体架构。停止旧回答要求继续有效。
- Supersedes: D-051的媒体架构实施授权；不改变既有取消要求，不授权外部调用。

#### D-052工程调查闭环（非新增用户产品确认）
- Q-042原A/B问题因“取消需要更换传输”前提未成立而撤下；原音轨清待发队列和补正式播放出口后，本地浏览器已验证旧合成答截短/Final接续。没有用户选择B或重新批准A的记录。
- 证据：verification/development-20261022-r19/与r20/；剩余精确回执/编号仲裁/弱网实机仍在tasks，不据此宣称全部RTC验收通过。

### D-053：仅授权两条虚构文本的Jev最小联调
- Status: Confirmed
- Date: 2026-10-22 (America/Los_Angeles)
- Source thread/message: 当前研发聊天，request_user_input_async call_3512fabce8bb4281be3eb0a437b21040，第0项用户回复。
- Confirmation quote: “授权本批测试（上限 US$0.01）”
- Decision: 仅向TypeSafe POST https://api.typesafe.ai/v1/systemone发送verification/jev-smoke-plan.json的两条虚构英文文本和固定测试指令，最多2次请求，总费用上限US$0.01；每次超时3秒，无重试，鉴权/限流/超时/返回异常立即停止。不发录音或客户数据、不调用ASR/TTS；Key仅本地读取，不落证据。公开单价核验为$0.042/M输入、输出免费；默认64k上限两请求理论费用$0.005376。
- Scope: jev-synthetic-smoke-v1；具体请求SHA-256见计划和delivery-status.json。一次执行权；失败或超时不得自动重放，不授权其他批次/厂商/部署。
- Updated artifacts: verification/jev-smoke-plan.json、delivery-status.json、研发自测证据。

### D-054：仅授权一次保留RTP的本地组合可行性验证
- Status: Confirmed
- Date: 2026-10-22 (America/Los_Angeles)
- Source thread/message: 当前研发聊天，request_user_input_async call_05ce90ba5cfa4a5f9fa31f04d9c9e6e8，第0项回复。
- Confirmation quote: “允许先做这次本地组合验证，保留 RTP 传输，不批准正式替换播放链路。任务与音频必须有可靠对应证据；验证任务对应、Final取消、编号仲裁、失败不伪报，任一关键项无法证明就停止报告。通过后给我看结论、延迟影响和兼容性风险，再决定是否采用。不批准数据通道传音频，不授权收费调用。”
- Decision: 只做离线/本地纵向可行性关口；优先证明真实编码/RTP音频与任务可靠对应，失败立即停止后续组合，不把推断当事实；不改正式播放链，不启用数据通道音频、不发厂商请求。通过也须先交结论/实测延迟影响/兼容风险，再决定采用。
- Updated artifacts: tasks、rtc-delivery-boundary、delivery-status及本地验证证据。
- Closes: Q-043；不授权正式采用候选，不覆盖D-052。

### D-055：Deepgram三ASR固定合成音批次授权
- Status: Confirmed
- Date: 2026-10-23 (America/Los_Angeles)
- Source thread/message: 当前研发聊天，request_user_input_async call_dd3a44ee3efb4116901de621d14072cb，第0项回复。
- Confirmation quote: “授权本批（上限US$0.10）”
- Decision: 仅按verification/deepgram-asr-batch-plan.json发送3段虚构英文合成音（共18.405375秒）至api.deepgram.com，测试Flux英文、Flux多语种、Nova-3英文。最多9条连接，每条附3秒静音、连接总时长不超过30秒，总费用上限US$0.10。无重试/重连；任何错误或范围证据缺失立即停止全批。不调用LLM/Jev/TTS，不发送客户数据，Key只本地读取。
- Scope: deepgram-td-asr-synthetic-v1；request_sha256=9cdcc4452e8437028f98abccd35814f25885af33dfa53a95759de19c8e93a74b；一次执行权，不能以失败为由重放。
- Updated artifacts: delivery-status.json、固定批次计划及执行证据。

### D-056：Jev显式保存Key控件允许偏离冻结原型
- Status: Confirmed
- Date: 2026-10-23 (America/Los_Angeles)
- Source thread/message: 当前研发聊天，request_user_input_async call_7a5bb7f552514d889885d5dc16e65e3d，第0项回复。
- Confirmation quote: “A：保留保存Key复选框（推荐）”
- Decision: 正式Jev连接页保留“为此Bot保存API Key”复选框，只有明确勾选才按Bot加密保存新Key。仅允许这一处控件偏离v0.14；冻结HTML及其SHA保持不变，其他样式/布局继续严格比较。本决定不授权外部调用或费用。
- Closes: Q-044。
- Updated artifacts: 原型说明、design、tasks、UI对照测试、交付状态与自测报告。

### D-057：Flux单连接范围定位批次
- Status: Confirmed
- Date: 2026-10-23 (America/Los_Angeles)
- Source thread/message: 当前研发聊天，request_user_input_async call_be090e8c5e8246b686048971132eb6da，第0项用户回复。
- Confirmation quote: “授权本次定位（上限US$0.02）”
- Decision: 仅向api.deepgram.com发送deepgram-asr-range-diagnostic-plan.json中原continuation合成音6.18925秒及3秒静音，Flux英文1连接、总时长≤30秒、费用≤US$0.02；首异常/范围缺口立即停，无重试。仅留白名单时间字段，不调用LLM/Jev/TTS，无客户数据；独立一次授权，不重放D-055。
- Updated artifacts: 固定批次计划、delivery-status.json及脱敏执行证据。

### D-058：Deepgram TTS三条固定文本批次
- Status: Confirmed
- Date: 2026-10-23 (America/Los_Angeles)
- Source thread/message: 当前研发聊天，request_user_input_async call_be090e8c5e8246b686048971132eb6da，第1项用户回复。
- Confirmation quote: “授权TTS本批（上限US$0.10）”
- Decision: 仅发送deepgram-tts-batch-plan.json固定one、two、Your number has been cleared.共35字符；固定flux-alexis-en，24kHz单声道PCM16，最多3次，每次15秒超时，总费用≤US$0.10；鉴权/限流/超时/格式异常立即停，无重试、不换voice，不调用ASR/LLM/Jev，无客户数据。
- Updated artifacts: 固定批次计划、delivery-status.json及脱敏执行证据。

### D-059：Flux重叠词修复确认单连接授权
- Status: Confirmed
- Date: 2026-10-23 (America/Los_Angeles)
- Source thread/message: 当前研发聊天，request_user_input_async call_bed921187b2941aaa07d07cf2e0e4560，第0项回复。
- Confirmation quote: “授权修复确认（上限US$0.02）”
- Decision: 新的独立一次授权，仅按deepgram-asr-range-diagnostic-plan.json向api.deepgram.com发送原continuation合成音6.18925秒加3秒静音、Flux英文最多1连接≤30秒、费用≤US$0.02；首异常或缺范围立即停止，无重试，不调用其他服务。D-057不重放。
- Updated artifacts: delivery-status.json及脱敏修复确认报告。

### D-060：保留RTP的隔离最小映射实验
- Status: Confirmed
- Date: 2026-10-23 (America/Los_Angeles)
- Source thread/message: 当前研发聊天，request_user_input_async call_bed921187b2941aaa07d07cf2e0e4560，第1项回复。
- Confirmation quote: “允许这次最小本地映射实验”
- Decision: 仅在隔离实验中补来源样本→编码/RTP范围→解码样本记录，先证明跨任务边界可靠对应；证明不了立即停止。不得替换正式播放器、不传数据通道音频、不收费；映射证明后才做Final/编号组合并报告延迟及兼容风险。
- Updated artifacts: tasks、rtc-delivery-boundary、delivery-status及隔离实验记录。

### D-061：ASR范围缺失达到最长等待后明确失败结束通话
- Status: Confirmed
- Date: 2026-10-23 (America/Los_Angeles)
- Source thread/message: 当前研发聊天，request_user_input_async call_f82028ad049a47c0a1067ed63867c092，第0项回复。
- Confirmation quote: “A：明确报错结束本次通话”
- Decision: ASR范围/身份缺口在本轮既有最长等待截止仍不能可靠恢复，明确记录ASR证据错误并结束当前通话；保留原转写和失败原因，不提交不完整用户消息、不执行工具，不无限挂起、不猜来源或自动降级。截止前有真实证据恢复可继续正常流程。不新增控件或时限参数，不授权外部费用。
- Closes: Q-045。
- Updated artifacts: voice-pipeline Delta、design、tasks、自测计划及delivery-status。

### D-062：Deepgram ASR修复后新完整批次授权
- Status: Confirmed
- Date: 2026-10-23 (America/Los_Angeles)
- Source thread/message: 当前研发聊天，request_user_input_async call_0cc945e8a4a54365aa11631d7c034e31，第0项用户回复，随后明确“继续”。
- Confirmation quote: “授权新批次（上限US$0.10）”
- Decision: 新的独立一次批次，严格沿用deepgram-asr-batch-plan.json内容/hash，仅3段冻结虚构英文合成音（唯一18.405375秒），api.deepgram.com，Flux英文/多语种/Nova-3英文最多9连接，每条3秒静音、连接≤30秒，总费用≤US$0.10；无重试/重连，首异常或范围缺失立即停止整批，不调用Jev/LLM/TTS、不发客户数据。不得借本批重放旧授权或增加诊断调用。
- Updated artifacts: delivery-status.json、r47脱敏执行证据及自测报告。

### D-063：Deepgram TTS修复后新固定批次授权
- Status: Confirmed
- Date: 2026-10-23 (America/Los_Angeles)
- Source thread/message: 当前研发聊天，request_user_input_async call_0cc945e8a4a54365aa11631d7c034e31，第1项用户回复，随后明确“继续”。
- Confirmation quote: “授权新TTS批次（上限US$0.10）”
- Decision: 新的独立一次批次，沿用deepgram-tts-batch-plan.json内容/hash；one、two、Your number has been cleared.共35字符，api.deepgram.com，固定flux-alexis-en、24kHz单声道PCM16，最多3请求、每次合成15秒，总费用≤US$0.10；首鉴权/限流/超时/格式错误停止整批，不重试/换voice，不调用ASR/Jev/LLM或其他厂商。
- Updated artifacts: delivery-status.json、r47脱敏执行证据及自测报告。

### D-064：Q-046保留RTP的有限候选实现授权
- Status: Confirmed
- Date: 2026-10-24 (America/Los_Angeles)
- Source thread/message: 当前研发聊天，紧接“Q-046是什么？”及A/B解释后的用户消息“A好的，就用A吧”。
- Confirmation quote: “A好的，就用A吧”
- Decision: 允许隔离候选保留RTP音频传输，补服务端任务范围映射、客户端解码/现有任务播放器与实际回执，验证映射/Final取消/编号仲裁/失败不伪报；任一关键对应无法证明即停止并报告。验证后报告新增延迟和手机兼容风险，正式采用仍待用户决定。不是数据通道音频、正式替换、泛用调查重启或收费测试授权。
- Closes: Q-046。
- Updated artifacts: open-questions、design、tasks、delivery-status及有限候选证据。

### D-065：TTS one最小单例修复确认授权
- Status: Confirmed
- Date: 2026-10-24 (America/Los_Angeles)
- Source thread/message: 当前研发聊天，request_user_input_async call_9b2d2cd5108c4172b0576a5e419cfe17 第0项用户回复。
- Confirmation quote: “授权此 TTS 单例（上限 US$0.02）”
- Decision: 仅按deepgram-tts-one-confirmation-plan.json向api.deepgram.com发送one共3字符，固定flux-alexis-en、24kHz单声道PCM16；最多1请求，合成超时15秒，总费用≤US$0.02。任何鉴权/限流/超时/协议/格式异常立即停止，无重试/换voice，不调用ASR/Jev/LLM，不发送客户数据。本批独立，不批准RTC继续，不重放D-063。
- Updated artifacts: delivery-status.json及r57脱敏执行证据。

### D-066：RTC解码坐标一次固定本地诊断授权
- Status: Confirmed
- Date: 2026-10-24 (America/Los_Angeles)
- Source thread/message: 当前研发聊天，紧接r57最终回复“仍等待那一次免费本地RTC诊断授权；本次TTS授权已用完”后的用户消息“授权”；对应此前单次本地诊断问题（题干“本次RTC组合已按约停止。是否允许一次最小本地诊断”）。
- Confirmation quote: “授权”
- Decision: 仅批准r54/local-diagnostic-proposal.json：本机1连接，两个各30ms本地合成音及原生静音总媒体≤1秒；记录首次不匹配的AudioData时间戳/率/帧数/pending坐标，首次不匹配或任意其他异常立即停，无重试，不重跑Final/编号、不换架构、不用数据通道传音频、不调用厂商、费用0。此答复不重新批准D-065或ASR付费测试。
- Updated artifacts: delivery-status、r58诊断与脱敏字段证据。

### D-067：保留RTP修复候选有限确认授权
- Status: Confirmed
- Date: 2026-10-24 (America/Los_Angeles)
- Source thread/message: 当前研发聊天，request_user_input_async call_b582248f1f024c22a6c81199cc2dfcac第0项回复。
- Confirmation quote: “允许这批本地修复确认（推荐）”
- Decision: 仅按r58/repair-confirmation-proposal.json，最多3个本机连接；先同两段30ms合成音的1秒映射关口，通过后才Final取消和编号仲裁各一次、各≤2秒源媒体，总≤5秒。任一失败停全批、无重试、不换架构/扩大时间容差，不调用厂商/产生费用，不替换正式播放器。D-066不复用。
- Updated artifacts: delivery-status、r59逐关口实际结果。

### D-068：受控正式RTC入口集成授权
- Status: Confirmed
- Date: 2026-10-24 (America/Los_Angeles)
- Source thread/message: 当前研发聊天，request_user_input_async call_8e0902bad4bb42be977e1fa1f22b39cf 第0项回复。
- Confirmation quote: “允许受控正式入口集成（推荐）”
- Decision: 仅开发环境接入正式RTC入口、现有鉴权回执与历史，并补同输入延迟对照。默认旧链不变、不加配置控件、不部署、不调用付费厂商；明确工程缺陷自行修复并定向回归，若任务对应无法证明或需要换架构则停止报告。不是正式默认采用、数据通道传音频、生产部署或付费授权。
- Updated artifacts: design、tasks、delivery-status与后续正式入口集成证据。

### D-069：正式RTC单连接有限诊断
- Status: Confirmed
- Date: 2026-10-25 (America/Los_Angeles)
- Source thread/message: request_user_input_async call_2afda2084c644c06a8f54383fafd5f1d 第0项用户回复。
- Confirmation quote: “允许这次有限本地定位（推荐）”
- Decision: 正式RTC入口最多1条本机连接，源音频最多2秒，只记录首次映射失败原因和包/解码计数；首次失败立即停止，无重试，不运行Final或编号组合，不放宽容差/换架构，不调用厂商，费用0。D-068已停止的批次不重放。
- Updated artifacts: tasks、delivery-status、诊断硬限制与实际证据。

### D-070：正式RTC发送接收分界有限定位
- Status: Confirmed
- Date: 2026-10-25 (America/Los_Angeles)
- Source thread/message: request_user_input_async call_354a271fc0cf4f9aa2be429369588cbf 第0项用户回复。
- Confirmation quote: “允许本批分界定位（推荐）”
- Decision: 同正式入口/0.1秒本地合成开场，最多1连接、含静音原生源最多2秒，仅补发送完成计数/浏览器收包和编码格式/播放器状态，首映射失败立即停，无重试/Final/编号/架构或容差更改/厂商调用，费用0。D-069不重放。
- Updated artifacts: delivery-status、r66固定执行与脱敏结果。

### D-071：正式RTC安装顺序修复确认
- Status: Confirmed
- Date: 2026-10-25 (America/Los_Angeles)
- Source thread/message: request_user_input_async call_132970f8b8d04c8d839a9eb5371808d0 第0项回复。
- Confirmation quote: “允许这次安装顺序修复确认（推荐）”
- Decision: 去掉测试原生分析器，提前安装transform；同正式入口0.1秒开场、最多1本地连接、含静音原生源≤2秒，只验证实际开播/结束回执。首次失败立即停、无重试，不跑Final/编号，不改架构/容差，不调用厂商，费用0。D-070不重放。
- Updated artifacts: delivery-status、r67固定范围与实际证据。

### D-072：手机端保留现有全局 Bot 列表顺序（Q-047）
- Status: Confirmed
- Date: 2026-10-25 (America/Los_Angeles)
- Source thread/message: 当前研发聊天，用户查看 http://127.0.0.1:8794/shell-comparison/ 后，在确认 A/B 仅影响手机窄屏布局的回复之后直接选择 B。
- Confirmation quote: “那就B吧，我看现在线上是B”
- Decision: 手机窄屏保留正式页面现有全局布局：当前页面内容在前，Bot 列表在后。仅允许这一处相对冻结原型的顺序差异；桌面布局、TD 内容、Share 卡片及其余冻结规则不变。不修改 v0.14 冻结 HTML 或其 SHA-256。
- Updated artifacts: open-questions、design、tasks、prototypes/README、ui-checklist、delivery-status。

### D-073：有误差边界的真实播放/E2E延迟范围（Q-048）
- Status: Confirmed
- Date: 2026-10-25 (America/Los_Angeles)
- Source thread/message: request_user_input_async call_6c1fabd31c084a71af7ca756f4dcf2fa 第0项用户回复。
- Confirmation quote: “A：接受带误差边界的范围（推荐）”
- Decision: 保持音频传输不变，补会话认证时钟关联、保存和正式历史指标展示；接受有证据和误差边界的播放/E2E延迟范围，证据不足显示缺失。禁止用收件时刻或假设上下行RTT各半伪造精确值，不回填旧历史。仅允许这一处指标展示差异，不更新冻结HTML/SHA；不批准默认播放器替换，不授权收费调用。
- Updated artifacts: Delta、design、tasks、prototype说明、ui-checklist、delivery-status及r76技术证据。


### D-074：运行时补合成失败保留采集并继续（Q-049）
- Status: Confirmed
- Date: 2026-10-25 (America/Los_Angeles)
- Source thread/message: 当前研发聊天，request_user_input_async call_70bb23ce7ad14c3abc113240e40ccba7 第0项用户回复。
- Confirmation quote: “A：跳过本次跟读并继续（推荐）”
- Decision: 缓存读取失败后的临时TTS补合成若也失败，跳过本次跟读，保留已采集编号并继续通话；历史明确记录补合成失败，不声称该任务已播放或成功完成。后续正常输入/受控工具仍可执行，不自动扩为新费用或无限重试。本决定不授权任何付费测试。
- Updated artifacts: open-questions、bot-config Delta、design、tasks、delivery-status、r83实际失败组合证据。

### D-075：新素材Flux英文单例修复确认
- Status: Confirmed
- Date: 2026-10-25
- Source thread/message: request_user_input_async call_2d4f597296ca42d5946e2af1cca717c0 item0；当前Codex用户回复
- Confirmation quote: 授权本次单例（上限US$0.02）
- Decision: 仅新虚构数字合成音5.1675秒加3秒静音发送api.deepgram.com / flux-general-en，最多1连接且总生命周期30秒；总费用上限US$0.02。首错误或范围缺失立即停止，无重试，不调用Jev/LLM/TTS，不复用旧授权。精确文件hash与请求范围以verification/deepgram-fresh-digits-confirmation-plan.json为准。

### D-076：Deepgram剩余两模型真实兼容
- Status: Confirmed
- Date: 2026-10-25
- Source thread/message: request_user_input_async call_09323e7e86894caf8873808c7aa72001 item0，当前Codex用户回复
- Confirmation quote: 授权两模型批次（上限US$0.02）
- Decision: 仅向api.deepgram.com分别发送同一新冻结5.1675秒虚构数字音频+3秒静音，固定flux-general-multi与nova-3英文，最多2连接、每条生命周期30秒、总费用US$0.02。首个错误或来源范围缺失停止整批，无重试，不重复Flux英文、不调用其他服务。范围/hash见verification/deepgram-remaining-models-plan.json。

### D-077：AssemblyAI固定3.5单例兼容
- Status: Confirmed
- Date: 2026-10-25
- Source thread/message: request_user_input_async call_d90c7ddae5a64b4a84cd88f428ee7173 item0；当前Codex用户回复
- Confirmation quote: 授权AssemblyAI单例（上限US$0.02）
- Decision: 只向streaming.assemblyai.com发送已冻结5.1675秒虚构数字音频+3秒静音，固定universal-3-5-pro英文；最多1连接、生命周期30秒、总费用US$0.02。首错误或来源缺口立即停止，无重试、不升级模型或调用其他服务。精确范围/hash见verification/assemblyai-single-digits-plan.json。

### D-078：Speechmatics Enhanced单例兼容
- Status: Confirmed
- Date: 2026-10-25
- Source thread/message: request_user_input_async call_741d5adf47734120b50ff9179262255a item0；当前Codex用户回复
- Confirmation quote: 授权Speechmatics单例（上限US$0.02）
- Decision: 仅eu2.rt.speechmatics.com，Enhanced英文，发送同一冻结5.1675秒虚构数字音频+3秒静音；最多1连接、生命周期30秒、费用US$0.02。首错误/范围缺失立即停止，无重试/换模型/其他服务，不改账号训练或留存设置。精确范围/hash见verification/speechmatics-single-digits-plan.json。

### D-079：Soniox固定v5基本兼容单例
- Status: Confirmed
- Date: 2026-10-25
- Source thread/message: request_user_input_async call_2f8d8d6c5e2e4de39eadc634dc8c7759 item0；当前Codex用户回复
- Confirmation quote: 授权Soniox单例（预算US$0.02）
- Decision: 只向stt-rt.soniox.com发送同一冻结5.1675秒虚构数字合成音+3秒静音，固定stt-rt-v5英文提示，最多1连接生命周期30秒，总预算US$0.02。按token计费，预留US$0.018预算和1000个接收token异常停线保护，明确不是厂商账号硬扣费封顶。首错误/范围缺口/token异常即停，无重试、翻译、上下文或其他服务。精确数据/hash与预算说明见verification/soniox-single-digits-plan.json。

### D-080：Final等待期间转写修订后采用新语义目标
- Status: Confirmed
- Date: 2026-10-26
- Source thread/message: 本评审对话 request_user_input_async call_8e1fe57ec4a1423eb7214ad45707690f item0；用户send_user_message_question_reply
- Confirmation quote: “按新 Jev 判断继续等，但不超过最长静音上限（推荐）”
- Decision: 已进入Final等待后，如果ASR文字修订，旧语义结果不能继续授权新文字提交；新有效Jev结果要求更长等待时按新目标等待，最长连续静音上限不延长。Final窗口到期不能绕过新目标。无新有效结果时按既有最长静音保护处理。不得无限重启Final等待或改变续说撤销契约。
- Updated artifacts: voice-pipeline Delta、design、tasks、independent-review、delivery-status。仅明确等待优先级；不授权外部收费测试或默认RTC采用。

### D-081：Flux英文否定与续说单例专项
- Status: Confirmed
- Date: 2026-10-26
- Source thread/message: request_user_input_async call_2015902983f5481a881e2a20a25fe1d4 item0；当前用户send_user_message_question_reply
- Confirmation quote: 授权本批（上限US$0.02）
- Decision: 只向api.deepgram.com/flux-general-en发送新冻结5.8576875秒虚构英文合成音“Please do not cancel my booking.”加0.8秒段间停顿及“I would like to change the time.”，尾加3秒静音；最多1连接生命周期30秒、费用上限US$0.02。首错误/来源范围缺失即停，无重试、不调用Jev/LLM/TTS、不发客户数据。未触发修订不得记通过或循环重跑。精确数据/hash见verification/deepgram-negation-continuation-r91-plan.json。预算非供应商账户硬扣费封顶，实际账单另记。

### D-082：真实Jev与既有ASR事件回放等待更新专项
- Status: Confirmed
- Date: 2026-10-26
- Source thread/message: request_user_input_async call_f115da4a2e6745e5934ab4157210d66c item0；当前用户send_user_message_question_reply
- Confirmation quote: 授权本批（上限US$0.01）
- Decision: 只向api.typesafe.ai/v1/systemone、固定jev-1.14.0发送两条既有虚构ASR文本“please do not cancel my booking.”和“please do not cancel my booking. I would like to”，以及冻结问题/助手提示；最多2次、每次3秒、总费用上限US$0.01。首错误/异常响应/范围缺口即停，无重试、不发音频/客户数据、不调用ASR/LLM/TTS。真实Jev加受控音频时钟检查D080；未形成更长等待或首目标已达Tmax就记未触发，不重复求通过。精确payload/hash见verification/jev-d080-replay-r92-plan.json。此授权不等于实时整链或RTC默认采用批准。

### D-083：启动本机Docker Desktop准备隔离资源测试
- Status: Confirmed
- Date: 2026-10-26
- Source thread/message: request_user_input_async call_0fb9baa336e94fcda9d796249444850e item0；当前用户send_user_message_question_reply
- Confirmation quote: 允许启动本机Docker Desktop，准备隔离测试
- Decision: 允许启动已安装本机Docker Desktop（已说明可能自动恢复旧容器），先只读检查现有状态，再另建1核1GB隔离测试；不改停旧容器或操作生产数据，不挂载真实DB/凭证。本授权不含外部付费API、部署、默认RTC采用、C或Gate2。

### D-084：Flux TTS取消与替换单例
- Status: Confirmed
- Date: 2026-10-26
- Source thread/message: request_user_input_async call_0dec3f8bfce648a9a72f07aac6b7496d item0；当前用户send_user_message_question_reply
- Confirmation quote: 授权本批（上限US$0.02）
- Decision: 仅向api.deepgram.com、flux-alexis-en发送verification/deepgram-tts-cancel-r94-plan.json冻结两条虚构英文共196字符，最多1连接/2Speak、24kHz单声道PCM16、生命周期30秒/取消确认2秒，总费用上限US$0.02（常规估算US$0.00882）。首异常即停，无重试/重连，旧合成已结束或无残留对应场景记未触发、不补跑。不发送录音/客户数据，不调用ASR/Jev/LLM；只验证厂商控制与SDK归属，不冒充实际客户端停播。账户硬费用封顶未验证，实扣另记。

### D-085：真实TTS与正式浏览器停播组合单批
- Status: Confirmed
- Date: 2026-10-26
- Source thread/message: request_user_input_async call_d748adb0a44f4fea9ea2d5958ea926c8 item0；当前用户send_user_message_question_reply
- Confirmation quote: 授权本批（上限US$0.02）
- Decision: 仅向api.deepgram.com/flux-alexis-en发送verification/deepgram-tts-formal-browser-r96-plan.json冻结两条虚构英文共196字符；最多1连接2Speak、24kHz单声道PCM16、连接30秒/取消确认2秒，总费用上限US$0.02（估算US$0.00882，未配置厂商硬扣费封顶）。正式页面验证旧答实际开播后由固定Final停止、新答随后开播；ASR/VAD/Jev/LLM为本地替身，不发送录音或客户数据。首异常或缺播放证据立即停止，无重试/重连；仅WS不启用RTC，不复用D084。服务端旧合成已完成可单独留证，但必须证明客户端仍实际播放并停止；不伪称真实ASR/LLM全链、手机/声学或Gate2通过。

### D-086：真实LLM工具专项暂保留未验证
- Status: Confirmed
- Date: 2026-10-26
- Source thread/message: request_user_input_async call_e8c8e7ade25e480da98a387da4af7e8f item0；当前用户send_user_message_question_reply
- Confirmation quote: 先保留未验证。
- Decision: D085真实TTS浏览器单例后，真实LLM工具专项暂不准备外部调用，保留未验证。尚无厂商/模型/接口域名及单批费用授权，不猜测选择或复用旧授权。这不是排除最终验收范围、接受该风险、确认完整C或Gate2。

### D-087：Gate2 配置页面分项用户确认
- Status: Confirmed
- Date: 2026-10-26
- Source thread/message: codex://threads/01a15c6b-12a0-7103-8ac7-8d41556c6731；配置页6项复验与重启截图后，用户消息“符合预期”（页面 http://127.0.0.1:18997/）。
- Confirmation quote: 符合预期
- Decision: 确认G2-01配置页面的布局和操作符合预期。仅为该分项产品确认，不扩展为真实语音效果、完整Checkpoint C、整个Gate2通过或外部付费调用授权。

### D-088：用户通过Gate2并接受剩余验证转线上
- Status: Confirmed
- Date: 2026-10-27
- Source thread/message: codex://threads/01a15c6b-12a0-7103-8ac7-8d41556c6731；本地收尾报告后用户明确发布指令。
- Confirmation quote: 我拍板通过了，这几项我没法在测试环境测。直接上线吧。我去线上测试
- Decision: 用户通过Gate2并授权发布当前已审核实现至既有线上环境，接受收尾清单中的真实模型组合、设备声学/手机弱网、RTC性能兼容及完整界面覆盖尚未验证的风险，将这些验证移至上线后由用户主导。此为用户明确接受风险，不把未测项改成技术PASS；不授权Agent自行运行付费厂商测试，不改变RTC默认传输或采用开发候选。部署继续遵循现有CI/健康检查/失败回退，排除无关工作区与敏感产物。

### D-089：授权原服务器数据库备份
- Status: Confirmed
- Date: 2026-10-27
- Source thread/message: codex://threads/01a15c6b-12a0-7103-8ac7-8d41556c6731；备份范围解释后当前用户消息。
- Confirmation quote: 可以创建备份
- Decision: 仅在原服务器 /home/deploy/backups/jev-20261027-pre-release 备份 bots.db、history.db，不复制录音、不传出服务器，目录700、文件600。最初自动审批因未明确授权额外数据复制拒绝执行；本次获明确授权后执行。检查发现自动CD已先完成，因此实际为上线后快照，已向用户披露，不能声称具备上线前数据回退能力。

### D-090：补齐Hello排查诊断
- Status: Confirmed
- Date: 2026-10-27
- Source thread/message: codex://threads/01a15c6b-12a0-7103-8ac7-8d41556c6731；说明缺少ASR原始事件与打断来源之后的用户指令。
- Confirmation quote: 那就补齐啊
- Decision: 补齐用于排查的ASR原始事件元数据及本地VAD打断来源；不改变识别/话轮/打断策略，不重新调用收费接口。沿用既有会话证据存储与留存，不额外保存全文、密钥或音频。旧会话无法追溯恢复未记录数据。此次生产更新须在补丁审核后明确确认。

### D-091：上线Hello诊断补丁
- Status: Confirmed
- Date: 2026-10-27
- Source thread/message: codex://threads/01a15c6b-12a0-7103-8ac7-8d41556c6731；明确询问诊断补丁部署后用户答复。
- Confirmation quote: 部署。
- Decision: 授权把D-090已本地验证及独立审核的诊断补丁部署既有线上环境；不更改识别/打断策略，不授权Agent发起收费通话或模型请求。
