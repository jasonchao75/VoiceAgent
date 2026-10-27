# r58：D-066单次本地诊断定位，离线修复待原生确认

## 已确认根因与实际边界

用户紧接r57唯一待答RTC项回复“授权”，记录D-066。执行前gate-before.txt先独立返回0、再核对输出，才原子创建diagnostic-claimed.json；单用例、--workers=1 --retries=0 --max-failures=1。只一对本机WebRTC连接，source由服务端限制≤24000个24k样本（1秒），两段30ms合成音及原生静音，Opus/RTP传音频、数据通道仅映射。未调用厂商/Key，无费用。

实际首不匹配处立即pc.close/worker.terminate，随后关闭服务（会话6417终止）；decoder-diagnostic.json observed.timestamp=1253499，pending=[1253500]，rate48000/frames960。对应source_start12168包hash已一致。唯一根因是代码把微秒时间标签当不可变身份做精确字典键，1us差导致无map，不是缺词/包身份丢失/样本数变化。不能说因此已证明所有浏览器时间误差机制或源码内部浮点实现。diagnostic.txt的1passed只表示成功捕获预定失败字段，不是RTC兼容通过。本批已消费，不重放。

## 离线修复，未进行新RTC运行

offline-red.txt用真实保存的1253499/1253500差值，模拟AudioDecoder但执行同worker代码，先1失败/1对照通过（真实extent差拒绝）。现RTPPacketDecoder一次仅接受一个已经payload hash/SSRC/原生PTS范围验证的包，保留同一Opus解码器；decode后等待flush把本job输出排空，要求恰当48k/960且只有一个输出，收齐再按原packet区间向Worklet发PCM。时间标签保留作诊断，不做任务身份、不匹配近邻、不改容差。新job不能与前job同时在途；缺输出/多输出/格式差仍失败。

依据是W3C WebCodecs AudioDecoder.flush：先完成控制队列并发出已有解码输出，再兑现flush promise；不是reset。原文入口https://www.w3.org/TR/webcodecs/#dom-audiodecoder-flush。此API契约支持单在途job绑定；原生浏览器/Opus跨包状态及每包flush新增成本尚未实测，不能用规范或mock当兼容证明。

offline-green.txt两个离线检查通过；运行命令node --test frontend/tests/unit/td-rtp-decode-job.test.js，无浏览器/RTC/网络。ruff与JS语法通过。源码副本candidate-sources-after-offline-fix.tar.gz和hash列出14个候选源/测试，明确晚于诊断输入，只供新修复审查，不冒充真实诊断时源码或Change归档；原r48阶段副本未改。

## 下一关口与停止纪律

repair-confirmation-proposal.json只是未授权的具体范围：最多3个本机连接，先同A/B固定1秒映射门槛（覆盖旧失败点）成功，才Final和编号各最多2秒源媒体，总≤5秒，任何错误/不明对应停止整批；无重试/新架构/费用/厂商调用。相关测试入口已准备，未执行：td-rtp-repair-gate.spec.js以及td-rtp-serial.spec.js，必须分别检查首门槛退出码后再运行组合，两个组合文件serial且--max-failures=1 --retries=0。旧D-066仅诊断，不能自动授权新复测。

风险：每包排空可能增加调度/解码成本；真实Opus状态和延迟不明，手机/Safari/弱网不在此小批范围；正式播放器不替换。ASR原固定WAV仍缺，TTS仅one单例已成功，整体实现/完整回归未完成，不自签独立PASS/C/Gate2。
