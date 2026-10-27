# 保留WebRTC音轨的最小取消方案（D-052）

## 结论
此前将“缺少逐任务精确播放计量”推导为“需要改下行数据通道PCM”证据不足。现有WebRTC音轨可以被打断/静音，不必据此更换传输。尚未证明现有完整通路能零残留取消；先定位现有通路，再以本地音频实验测量。

## 实际证据
- 锁定Pipecat 1.8.1，transports/base_output.py:566的handle_interruptions取消/重启输出任务或reset音频队列，并发送bot stopped speaking。这是后端打断能力，不是客户端已停播证明。
- smallwebrtc/transport.py:76 RawAudioTrack维护独立_chunk_queue，以10ms拆分PCM；write_audio_frame在446等待add_audio_bytes的Future。该类未提供清空方法；取消等待Future不会移除已排队PCM。
- [本地实际SDK实验](webrtc-queue-probe.txt)：100ms恒定非零PCM、10个10ms块，Future取消后仍10块；recv继续返回旧非零音频。无网络/外部API。这定位的是一层缓冲缺口，不能据此断言RTP协议无法取消。
- 锁定SmallWebRTC JS 1.10.7有远端track事件和tracks()；mute/unmute回调表明媒体可用性，不代表具体回答最后一个采样已渲染。
- 浏览器可以[禁用MediaStreamTrack输出静音](https://developer.mozilla.org/en-US/docs/Web/API/MediaStreamTrack/enabled)，也可以[pause媒体元素](https://developer.mozilla.org/en-US/docs/Web/API/HTMLMediaElement/pause)。两者不能被当作RTP接收/抖动缓冲已清除，也不是硬件声音立即停止保证。

## 最小改动分层
1. 保留现有Opus/RTP音轨、上行和信令。取消旧LLM/TTS生成，现有响应代次隔离继续拒收迟到旧音频；接现有SDK输出打断。
2. 补清SDK RawAudioTrack待发PCM与未完成等待者，避免只清上层队列。用取消前后非零样本/新回答样本区分的回归验证；不改依赖文件。
3. 如实际网络测试仍有可听尾音，再补浏览器当前音轨的临时静音控制及带请求代次回执。它能抑制收到控制后的音轨输出，但旧包跨网络迟到和何时恢复新答必须单独验证，不以固定等待或控制消息顺序假装音频边界准确。
4. 若必须做到逐任务精确采样计量/严格零旧样本恢复，需要进一步研究媒体时间戳与渲染边界。此要求不能与“用户能打断旧答”混为一谈，也不能直接决定数据通道替换。

## 能做到/未保证
目标是阻断旧生成、清理待发旧音频，验证现有音轨打断后的实际残留和新答衔接。后端静态与队列实验只证明具体缓冲缺口；尚无浏览器网络取消残留、弱网、手机/蓝牙实测，不能承诺零尾音或精确硬件时间。现阶段建议先实施/验证保留音轨的工程修复，再按证据评估是否有必要更大改动。A无实施授权，未改媒体代码。
