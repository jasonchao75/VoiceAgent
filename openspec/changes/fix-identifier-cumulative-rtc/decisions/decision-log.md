# Decisions

### D-001
- Status: Confirmed
- Date: 2026-10-27
- Source thread/message: codex://threads/01a15c6b-12a0-7103-8ac7-8d41556c6731，最新用户指令。
- Confirmation quote: 那就按这个方案修吧，把累计转写和RTC跟读接线这两个问题一起修好，先自测和审核，通过了再给我上线。
- Decision: 按来源替换本地编号修订并修复正式RTC跟读链路；自测/独立审核通过后授权上线，不授权收费API测试。

### D-002
- Status: Confirmed
- Date: 2026-10-27
- Source thread/message: codex://threads/01a15c6b-12a0-7103-8ac7-8d41556c6731，2026-10-27 用户要求修复连接失败占用名额，并确认 Task playback is unavailable 的消息。
- Confirmation quote: 那你把连接失败后不释放名额的问题修好，浏览器兼容性也一起查清楚，别让我一直反复试了。现在报错是Task playback is unavailable in this browser。你做的跟读播放器有问题？
- Decision: 修复未连接失败的名额释放并查明兼容性，不静默取消跟读或更换音频传输架构。

### D-003
- Status: Confirmed
- Date: 2026-10-27
- Source thread/message: codex://threads/01a15c6b-12a0-7103-8ac7-8d41556c6731，用户最新要求浏览器兼容适配。
- Confirmation quote: 为什么跟读还需要另一套音频接口？我刚下载了一个chrome尝试访问，也不行。你能做好兼容适配吗？
- Decision: 实施新旧浏览器RTP编码流接口兼容适配，保留同一任务身份、解码和播放证据，不新增传输协议或付费调用。

### D-004
- Status: Confirmed
- Date: 2026-10-27
- Source thread/message: codex://threads/01a15c6b-12a0-7103-8ac7-8d41556c6731，用户要求继续修复Unable to connect to transport。
- Confirmation quote: 那你继续查清楚并修好啊，别只补日志。自测和审核通过后再上线，别让我一直反复试。
- Decision: 继续复现和修复连接后播放失败，自测及独立审核通过后上线；不授权付费外部测试。

## D-20261028-KEEP-IDENTIFIER — Confirmed
- 日期：2026-10-28。
- 来源：当前对话，用户在逐条核查PC累计跟读时的消息（以以下原话定位）。
- 用户原话：“我不想关闭数字跟读功能，这是本次很重要的一个功能。”
- 结论：保留数字跟读功能；不执行此前建议的关闭数字跟读/编号收集止损配置。继续独立定位RTC播放身份失败、增量跟读及ASR来源问题，不以关闭核心功能替代修复。

## D-20261028-RECORDING-SAMPLE — Confirmed
- 日期：2026-10-28。
- 来源：当前对话，展示935dbcf8录音27–42秒片段后的用户消息。
- 用户原话：“这段音频可以。另外，你的修复方案写一个文档出来，我看下你的计划”。
- 结论：认可该片段作为复现样本，授权编写评审计划；不代表逐字参考答案已核定，不代表原生播放取舍已确认，不授权真实外部收费调用。


## D-20261028-NATIVE-PLAYBACK — Confirmed
- 日期：2026-10-28。
- 来源：codex://threads/01a1822c-48f9-7370-b412-52f1bfdd5051，本轮用户对“核心取舍”回复的Annotation 1，以以下原话定位。
- 用户原话：“可以，我接受，让浏览器播放，减少故障发生的概率。允许多响一小截，同时系统不精确知道我听到哪里了”。
- 结论：接受恢复浏览器原生播放、允许短暂缓冲尾音及无法精确确认任务听到位置；保留数字跟读和编号收集。不构成Final重答策略变更、具体尾音数值验收、部署或付费测试的新授权。实施前仍需同步受影响规格、设计和任务。


## D-20261028-FINAL-CONTENT-RESTART — Confirmed
- 日期：2026-10-28。
- 来源：codex://threads/01a1822c-48f9-7370-b412-52f1bfdd5051，本轮用户要求更新repair-plan.md的消息。
- 用户原话：“可以，Final文字相同或只是标点、空格变化就不要重答，内容确实变了再重答。结合前面确认的原生播放方案，把repair-plan.md更新一下，我再看一遍。”
- 结论：Final相同或仅标点、空格变化不取消原回答；实际内容变化才重答。保留有界Final等待和Partial先响应。当前仅授权更新方案与决策记录，正式实施前同步相关行为规格、设计与任务。

## D-20261028-IMPLEMENT-REPAIR — Confirmed
- 日期：2026-10-28。
- 来源：codex://threads/01a1822c-48f9-7370-b412-52f1bfdd5051，本轮实施授权消息。
- 用户原话：“然后你开始修复吧。修复之后，自测、部署，上线后通知我复测。记得你自测的时候要用刚才另一个任务截取下来的那条音频。”
- 结论：按repair-plan实施、自测、独立审核后部署并通知复测；使用私有15秒样本。本授权不包含发送客户音频到收费厂商；需要时另行限定授权。
