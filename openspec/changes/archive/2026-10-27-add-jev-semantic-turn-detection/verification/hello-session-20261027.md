# Hello会话只读诊断

线上1b72ddd3-b6a6-49e6-bff3-5ce958263185：VAD多次开口/停顿但仅两组Hello转写；TD事件约14s/34s收到文字，首次产生LLM回复及TTS音频，第二次提交约0.57秒后触发interruption且无回复。Jev两次200/197ms和161ms，Qwen首次200。客户端最终end_reason=user。未检查录音和原始厂商事件，不能区分真实重复说话/回声/噪声，不能确认ASR前端或厂商漏字原因；实际首播无回执证据。

未发起厂商调用，未修改线上参数。下一步以已保留音频对照VAD时间轴和ASR来源事件定位；不能用降低VAD阈值替代诊断。

## 离线排查补充
- 指定录音下载到本机 /tmp/voiceagent-hello-review-20261027/uplink.flac，仅本地，不提交Git或上传第三方；16000Hz单声道，927984 samples=57.999s。不是全静音，5秒窗口RMS约-49.7至-27.7dBFS。音量分析不能证明每个声音是Hello或排除回声，本轮未完成人工听辨。
- 本地Pipecat Silero重放：confidence0.8与0.7、start/stop0.1s、min_volume0.6，均产生多次短语音状态；0.7扩大检测范围，不证明能修复ASR。结果 /tmp/voiceagent-hello-review-20261027/vad-replay.json，脚本replay.py，日志replay.log。离线固定20ms分块不等同线上输入分块/状态，不作为逐事件精确复现。
- 当前发布ASR为Nova3/en，interim_results=true、endpointing_ms=50、smart_format=true。此为当前快照，不冒充会话冻结参数。
- 代码检查：TD输入处理后继续传递音频给ASR，不以Silero阈值裁掉静音音频；Deepgram接收层对非空转写派发，无按confidence过滤。缺少这通原始ASR响应/发包证据，不能证明厂商未返回或排除适配丢失。
- 09:31:24.679首轮LLM请求，09:31:26.026产生TTS，09:31:28.246打断；09:31:44.081第二轮LLM请求，09:31:44.640打断。Jev非阻塞点。
- 额外日志观察：LLM上下文开场白出现两次，待检查聚合去重；不认定其为本次主因。
- 尚无足够证据区分真实用户声音/回声/噪声，没有实际客户端首播确认；没有重跑收费ASR。
