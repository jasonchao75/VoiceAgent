# 后续状态更新：D084/r95已执行

本文件的待授权/未执行叙述是r94修复准备时点；用户随后明确批准D084且单批已完成，当前真实结果见../development-20261026-r95/README.md。r94源码未变化，不能重放已消费授权；浏览器/物理停播边界不变。

# r94 Flux TTS取消边界修复与最小真实专项（2026-10-26）

用户本轮选择“先做TTS取消”，真实LLM工具测试暂缓，**此选择不是费用授权**。根.env只核对变量名，未给客户端加载LLM Key/未解密Bot凭证；本地测试Bot表为空，未访问Docker旧服务数据。TTS真实批次仍需本轮具体授权，不复用旧额度。

## 已复现的工程缺陷

Deepgram Flux二进制音频没有逐帧speech_id，锁定SDK按当前本地context归属；Interrupt与SpeechInterrupted之间旧包仍可能在途。此前新Speak可在取消回执前发出，旧PCM因此可被盖上新response身份。实际factory/scoped SDK两条离线回归先失败，已保留boundary-red；这不是声称已抓到真实厂商残留。

依据[官方取消协议](https://developers.deepgram.com/docs/flux-tts/interrupt-handling)：本地停播应立即执行，取消到回执之间音频应丢弃。此前仅测试显式旧context拒绝不足以覆盖无context的原始wire入口。

## 当前修复机制

- ConfirmedDeepgramFluxTTSService在取消时立即关闭接收屏障，只发一个Interrupt；SDK原有本地队列清理/停播控制不等待发送回压，网络发送作为会话持有任务，有界并在disconnect/cleanup取消加入。
- 下一条Speak必须等取消确认；旧PCM和旧SpeechMetadata在屏障内丢弃，后者不能关闭新分配context。NO_ACTIVE_SPEECH/NO_AUDIO_GENERATED是无活动合成的终止边界，普通逻辑可释放，但专项把它记未触发、不重跑。
- 等待沿用从取消发起算的2秒截止，不为新回答重启计时。超时/发送失败/断连后不再发新Speak，下一合成报永久错误；不靠猜测继续。新TTS可能增加一次取消确认往返，最长失败预算2秒；不改TD最长静音/Final规则，不新加页面字段。
- 共享Flux适配器使用同一协议防护，正常无取消路径没有新增网络往返；没有换RTP或默认启用RTC，没有服务端AEC。真实原生/off组合与真实等待分布尚未验证。

## 实际可本地验证

actual factory的wire回调与完整锁定SDK队列已覆盖：迟到旧音、新Speak等待、旧完成消息、超时不假放行、单Interrupt、无活动合成warning，以及发送回压不阻止本地控制。原Configure确认回归及新取消执行器FakeSocket保持原解析/队列，只替换网络。定向结果见final-related；当前最终candidate-backend为773通过、9可选Docker未启用、10依赖警告、37.71秒；Python3.11 mypy目标79源及Ruff4文件通过，均在本目录，不把不同中间版本计数相加。

最初测试遗漏voice、Sink未向下传StartFrame、新执行器WorkerRunner.add_workers未await/误传list均在任何收费调用前被离线检查发现并修正，错误日志保留，不当产品缺陷或厂商失败。backpressure-red是真实provider hook阻塞复现，改独立发送后通过。旧中间全量770通过属于发送任务分离前版本，最终以final-backend日志为准。

## 最小真实批次（尚未执行）

../deepgram-tts-cancel-r94-plan.json固定全文/hash：两条虚构英文共196字符，flux-alexis-en、24k单声道PCM16、速度1/expressivity0；最多1连接/2个Speak、全生命周期30秒，首错误/范围身份/格式/预算异常即停，无重试重连，不调用ASR/Jev/LLM。

预计按[官方价格页](https://deepgram.com/pricing)2026-10-26 Flux US$0.045/千字符计算US$0.00882，总预算请求US$0.02；账户硬扣费封顶未验证。合成若已结束或无残留，则对应场景未触发，不重复求通过。只以provider SpeechInterrupted证实取消边界，绝不用audio_played_ms代替客户端实际播放；新PCM需有新响应身份。该批**没有浏览器/扬声器/RTC真实停播证据**。

新增scripts/evaluation/probe_td_tts_cancel.py默认dry-run，授权/hash/独占claim均在Key读取前核对；精确Speak序列和控制消息在实际发出前检查，失败不退还预算，禁自动重连。tests/test_td_tts_cancel_probe.py通过内存socket验证完整取消/替换与“已结束不发第二条”路径，实际SDK其余逻辑保留。

## 边界与下一步

当前尚无本批真实外部结果：等待针对两文本/厂商/次数/费用/停止条件的用户回复；同时做源码独立复审。若获授权，按批次只运行一次，失败先分析已留日志，不能消费旧授权重放。LLM按用户选择暂缓；手机/Safari/弱网/物理双讲AEC/完整性能及实时厂商整链继续未验证，完整C/Gate2不签。

临时/tmp/voiceagent-r94-*为本轮检查日志；将来实际合成音属于虚构数据，若保存需在忽略test-results内并记录hash，不能提交Key/DB/录音。原r93镜像是此前源码产物，不冒充已包含本修复或真实TTS负载容量。

## 独立生命周期复审与当前交付

初次独立复审发现ACK先于send/drain完成后，第二次取消覆盖单一sender引用，旧任务可能漏join并回写新状态。先补两条失败回归，再以任务集合完整所有权、每任务捕获generation/deadline及有效确认代次隔离修复。旧发送失败不污染新代/已确认边界，cleanup/disconnect join全部未完成任务。原独立复现first_survived_join由true→false，支持关闭；旧BLOCKED和错误日志保留，当前见stage-review/repair-review-r94.md。

candidate-backend.txt/JUnit对应最终生命周期修复；此前770/771次版本日志只是中间阶段，不代表当前新增失败，也不与当前总数相加。9个skip是原生Docker显式开关未启用，本轮未改Docker规则，沿用r93独立9绿，不偷偷跳过TTS修复场景。没有复跑不受影响的前端/客户端或资源场景。

本轮仍无真实厂商调用、付费专项待用户明确答复；修复实现和离线自测可交审核，不能签真实取消兼容、完整C或Gate2。
