# r95 D-084真实Flux TTS取消单例独立证据核查（2026-10-26）

**限定结论：本批授权、执行输入与真实控制/SDK PCM证据相符，未发现新增确认缺陷。全产品仍INSUFFICIENT EVIDENCE，不签全Change PASS、完整C或User Gate2。**

本次按change-verifier只读核对，未执行API、测试、浏览器或Docker，未重放已消费授权，不修改实现/基线。原r94工程与生命周期返修结论保持，本次只补真实厂商限定事实。

## 授权与执行身份

- D-084记录用户回复`call_0dec3f8bfce648a9a72f07aac6b7496d`及原话“授权本批（上限US$0.02）”。范围为api.deepgram.com、请求voice flux-alexis-en、冻结196字符、1连接最多2Speak、24kHz单声道PCM16、总30秒/取消确认2秒，首异常停，无重试/重连/ASR/Jev/LLM或客户数据。
- 独立重算请求hash与计划/当前confirmed且completed的grant/原始claim一致：`3be31d39bd9b083a0d0c680d0226452e7557e87cc69d3137fc86ff61a5649432`。不是把先做TTS取消的优先级决定当费用授权；本批有独立D-084许可，当前已消费不可重放。
- r94/source-sha.json五项实际文件hash均与当前一致，包含已复审生命周期修复、执行器/对应测试及冻结计划。没有拿源码变化前的回归代表新执行器。原始ignored日志与交付jsonl副本字节完全相同；日志有独占claim，不含Key/headers/音频。

## 真实控制与PCM事实

原结果为status=ok、connections=1、speak_attempts=2。outgoing严格为`Speak→Flush→Interrupt→Speak→Flush`；incoming为`Connected→SpeechStarted→Flushed→SpeechInterrupted→SpeechStarted→Flushed→SpeechMetadata`。

执行源码guard要求新Speak必须等acknowledged_cancel；该状态仅在SpeechInterrupted的speech_id匹配首SpeechStarted、且Interrupt已发出时设置，任何不符会停止并非ok。两个保存的speech_id hash不同。这里的身份结论依赖**已核hash的执行guard与安全结果**，没有伪称交付日志保存了未经脱敏的所有原始消息。

- 取消发出至ACK之间实际收到19200字节二进制PCM；按请求/SDK的24k PCM16单声道换算为9600样本、400ms**生成音频量**。此时尚未允许新Speak，屏障丢弃这些在途字节；接受的旧response身份SDK输出after-cancel为0。
- 新response身份SDK输出49920样本，按24k换算2080ms。格式/来源由实际SDK输出guard校验，不是“已经播放2080ms”或物理扬声器事实。
- 本次确实观察到取消区间在途音频，不是未触发残留就计通过，也不是仅FakeSocket演示。但没有逐字听感/新音频内容质量评测，不能从SDK身份推导完整语音质量。

一个SpeechMetadata白名单计费字符值31被记录，不能据此说全部196字符最终收费只有31。全部固定文本按已记录US$0.045/千字符重算估算上界US$0.00882一致；实际美元账单为null/未知，预算US$0.02不是厂商硬扣费封顶。

## 可关闭的限定缺口与未验证

本批支持所请求voice/格式/两条固定文本下的**真实TTS Interrupt确认、取消前后wire屏障及新SDK响应来源**。不再把本案例标为“从未真实执行TTS取消”，也不把当前授权写成待回复。

没有浏览器/AudioWorklet网络组合、客户端实际停止、物理扬声器/RTC、ASR/Jev/LLM整链、取消延迟分布、其他voice/provider/language或容量证据。inflight PCM时长不是取消往返时间；无时间轴分布也不报告P95。后续如需这些范围，应新冻结精确数据/次数/费用/停止条件独立授权，不能重放D-084。

只读核对研发最终门禁0 errors/37 warnings；本次没有重新运行门禁或测试。当前复用r94实际已保存最终回归/类型证据，r95无代码变化不重复全量。完整独立C、用户Gate2和默认RTC采用仍未通过。
