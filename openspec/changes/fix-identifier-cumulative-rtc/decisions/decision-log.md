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
