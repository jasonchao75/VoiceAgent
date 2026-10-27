# 同输入本地对照及RTC风险报告

## 实际完成
D-068开发范围，同一正式public demo入口、相同2400 samples/24k mono PCM16、220Hz虚构开场（source hash见comparison.json）；锁定本机Chromium、假麦克风、ASR/LLM/TTS离线替身。旧链通过未改动的HTML播放器，candidate通过RTP/WebCodecs/任务Worklet。各1次有效观测，不扩大统计样本，不调用厂商。

## 测量起止与时钟
起点：同一浏览器performance时钟接收首bot-started-speaking控制消息；终点：观察AudioWorklet检测首个abs(sample)>0.001输出量子后主线程收到回调。另存getOutputTimestamp投影估计，非硬件采集。开播控制事件本身不当作实际播放，必须观察非零样本；起点不在用户停说/ASR/服务端，所以不是E2E。

| 支路 | 控制消息→观察回调 | 控制消息→输出时间戳估计 | 样本量 |
|---|---:|---:|---:|
| 原链 | 41.100ms | 65.607ms | 1 |
| 候选 | 25.900ms | 47.462ms | 1 |

## 关键限制
原链captureStream→MediaStreamSource只读支路观察播放器内容，探针经零增益防双播；原HTML输出不被重新路由。候选观察器直接接任务Worklet输出。原链捕获桥自身延迟未校准，因此不能从两数相减认定候选更快、确切新增延迟或满足P95。两支路控制事件/音频也有独立网络调度。当前有效结论仅为本地两条实际输出可观测，未测出可归因的额外延迟。

首次观察器重复加载模块，修复后MediaElementAudioSource路径仍未取到输出；原始两次失败分别保留，不当作产品原链失败。停止该观察法，改为W3C定义的媒体元素captureStream只读采集（https://www.w3.org/TR/mediacapture-fromelement/），同数据两支路各通过。测试构建/仪器不修改正式架构。

## 兼容与采用边界
- 默认旧链保持；开发构造参数显式启用candidate，不加产品控件、不部署。
- 候选需要RTCRtpScriptTransform、AudioDecoder/Opus和AudioWorklet；只有当前Chromium实际证据，手机、Safari、Firefox及目标机器未知，不用API存在冒充兼容。
- 网络重传/丢包、浏览器后台/节电、真实扬声器/耳机/AEC、Opus听感、目标1CPU/1GB以及长会话实际容量仍未验证。
- 每包串行decode+flush局部耗时证据沿用r59，不将其相加冒充E2E。
- 服务端使用锁定SDK私有队列/编码适配，升级需定向回归。来源记录已消费释放有离线长序列证据，不证明真实长通话。

## 下一步与产物
Final/编号组合正式证据分别r68/r69；本报告补上本地同输入对照与局限，不标独立PASS/C/Gate2/正式采用。严格新增E2E需校准采集或受控硬件回环，当前保持未验证。测试DB/录音/主密钥在/tmp/voiceagent-d068-latency-native与-candidate，原始/tmp/voiceagent-r70-*-server.log含临时能力/本机网络，忽略不提交。
