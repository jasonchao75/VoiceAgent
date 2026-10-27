# D-052后续：保留RTP的渲染身份调查（r35）

## 当前结论

旧回答取消已有r19/r20队列与正式页面RTC证据；精确逐任务播放回执仍未接通。不能从“接收到编码帧”“轨道数据更新”直接认定已经实际输出声音，也不能据此恢复被撤回的数据通道PCM方案。此文是工程调查，不改变产品决定或宣称完成。

## 本地依赖事实

锁定aiortc/rtcrtpsender.py的_run_rtp给编码时间戳加随机timestamp_origin后发RTP。原始PCM/source-frame时间不是直接可拿到的线路RTP时间戳；真正建立映射需覆盖随机起点、48kHz编码时钟、重采样/编码分帧及跨包边界。现有TaskAudioFrame身份没有穿过这一路到浏览器解码帧。

## 官方API语义

- [WebRTC Encoded Transform](https://www.w3.org/TR/webrtc-encoded-transform/#rtcencodedframemetadata-dictionary)提供RTP/接收/捕获时间相关字段；编码变换位于解码之前，receiveTime表示帧所需最后一个包的接收时间，不能据此填写实际开播。
- [WebRTC getSynchronizationSources与字典](https://www.w3.org/TR/webrtc/#dom-rtcrtpreceiver-getsynchronizationsources)的更新发生在帧交付接收track时；规范特别说明即使没有连接播放sink也会更新。因此单独使用此API不能证明P11实际开播。
- [MediaStreamTrack Insertable Media Processing](https://www.w3.org/TR/mediacapture-transform/#introduction)仍说明音频track处理尚无工作组共识。不能因为本机暴露构造器就宣称跨浏览器/手机支持。

均为只读官方文档查询，未访问厂商账户或推理接口。

## 实际浏览器探测

测试源frontend/tests/ui/td-rtc-capabilities.spec.js：请求由测试进程截获，仅本机安全origin，不访问应用API；本地振荡器产生测试音、零增益图拉取，不读麦克风、不输出可听声音。不是新增产品页或UI A/B验收壳。

Chromium153实际暴露Encoded Transform、receiver.transform及MediaStreamTrackProcessor。首次未维持音频图拉取，AudioData读取超时；加入零增益拉取后读到真实AudioData（48kHz、480帧），具有timestamp但无直接rtpTimestamp。日志capabilities.desktop-chromium.json只记录能力/时间字段，不保存PCM或凭证。此事实证明解码音频API可用，尚未证明它与网络RTP、任务或硬件输出的关联。

另建无STUN的浏览器内peer对，试图验证无sink时的同步来源更新；两次均停在ICE connecting/checking，没有RTP观测。关闭测试mDNS隐藏的尝试也未成功，不能据此推断根因。失败输出保留browser-probe-with-rtp.txt/browser-probe-no-mdns.txt；最终测试保留为VOICE_AGENT_TD_RTC_PAIR_PROBE=1显式启用的诊断，默认跳过，不计为通过。默认能力探测1通过/该诊断1跳过只是执行结果，不是RTC任务回执实现通过。

## 后续工作边界

继续研究保留RTP时发送侧任务/编码范围与客户端实际渲染边界的关联，先用可重复本地网络实验验证，不将发送完成/接收回调/无sink时间戳伪造为播放事实。现有原音轨取消能力不因此被推翻；真实手机、硬件时间、丢包/抖动、完整编号缓存/串行仲裁仍未闭环。任何新架构或产品取舍须另列证据并按项目规则处理，不擅自批准A。


## r36本地RTC连通与播放器对照（新增实际证据）

不删除r35失败记录。默认参数下两端各1个mDNS候选，ICE checking/DTLS new；改用与既有RTC测试相同的Playwright虚拟采集权限、虚拟媒体设备并保持虚拟采集时，两端候选14/7，ICE/DTLS connected。该对照只证明本机诊断在此条件下可连通，不证明权限是所有环境ICE失败的唯一原因，也不是生产网络修复。

连通后，无播放器阶段已收到250个RTP包，但jitterBufferEmittedCount、decodedFrames及同步来源观测均为0；TrackProcessor单独读取未使此版本远端音频开始解码。添加静音HTMLAudioElement并play后，取得12个真实AudioData及5个变化的RTP同步来源观测。没有真实麦克风、可听音频输出、客户数据或厂商调用。收包、解码、播放出口必须分开留证，不能将250包当作250次播放。

最后的有限时间样本为48kHz、每帧480采样；相邻AudioData.timestamp差为5.6～10.8ms，尚未给出它与网络RTP戳按单一固定偏移精确一一对应的证明。不同API的时间域、异步交付和播放进度不能静默套公式填成真实任务时间。

测试改为先记录无播放器阶段，再观察静音播放器对照；r35“无任何播放sink时必须看到同步来源更新”的正向测试假设未在本机复现，不能将原失败改称通过。r36新对照明确验证的是不同阶段差异，未验证规范全部实现一致性。执行需VOICE_AGENT_TD_RTC_PAIR_PROBE=1；默认仍为可选诊断，不属于正式UI A/B或任务回执通过。日志与有限JSON见development-20261022-r36/；JSON不含地址、SDP、PCM或凭证。

下一步仍需在保留原RTP的正式任务音频上建立并验证发送侧任务边界→编码范围→客户端实际输出的对应。以上实验不解除R35任务映射Open，也不批准更换下行传输。
