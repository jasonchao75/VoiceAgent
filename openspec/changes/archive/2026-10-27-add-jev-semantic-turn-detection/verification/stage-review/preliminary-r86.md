# r86 独立增量审查（2026-10-25）

**整体结论：BLOCKED。** 这是RTC上行来源前置机制的阶段审查，不是最终Checkpoint C，不设置PASS或User Gate 2。评审使用change-verifier，只读实现；未重跑浏览器、厂商、旧有限RTC实验，未修改代码。

## 审查范围与结果

- 已追踪开发候选`create_small_webrtc_transport(candidate_playback=True, custom_td=True)`→`install_candidate_input`→receiver timestamp mapper/decoder queue→原生track/AV resampler→未改动的SDK音频帧。默认RTC不安装该钩子；custom_td=False候选拒绝。前端仅受控候选安装sender metadata观察，仍走RTP，不发数据通道音频。
- 锁定aiortc包处理中，SSRC由ContextVar保留到原始handler；timestamp map后decoder queue put之间无await，旁路保留原mapper结果及原始编码帧payload。SSRC首次稳定保护拒绝混源，任何变化使该ledger永久不再证明，不能拿当前到包SSRC冒充旧jitter输出来源。RTX/异常混源可能丢失证明，但不会因此声称已支持重连。
- decoder PTS只在真实48k Opus AV帧且存在相同PTS编码证据时接入。processed位置取真实resampler输出time_base/pts，不拿raw.pts代替；覆盖必须连续、无重叠歧义，并以实际输出PCM hash校验。第二块16k PCM跨前一编码包尾部的事实有原生测试，未替换codec/resampler或重算PCM。
- encoded/decoded各256、冲突deque及processed待对64有界。native reader正常关闭/异常关闭finally恢复track/resampler；receiver恢复仅限仍由本observer持有的方法/queue。观察结果是附加metadata，音频帧本体、采样率、声道、raw.pts保持。
- sender TransformStream原样enqueue同frame；hash用payload复制异步计算，不等待hash才能发音频，最多8条未ack。无原生captureTime就明确缺失，不用performance.now补值。sender transform安装失败只发能力缺失，不关闭已装receiver播放；close终止worker。此处仍不能证明零附加延迟或手机能力。

本次有限核查**未发现新增实现缺陷**。以上对锁定SDK、单稳定SSRC正路的源码与离线证据成立，不扩称弱网/RTX/跨SSRC/真实重连已验证。

## 独立执行与证据核对

| 检查 | 独立实际结果 |
|---|---|
| 新输入/开发入口/既有RTP与取消定向 | `pytest tests/test_td_rtp_input.py tests/test_td_rtp_integration.py tests/test_td_rtp_writer.py tests/test_td_webrtc_cancel.py -q`：16 passed /1依赖警告/1.05s |
| sender旁路/optional能力客户端 | `node --test frontend/tests/unit/td-rtp-input-tap.test.js frontend/tests/unit/td-rtc-entry.test.js`：6 passed /0 failed |
| 结构门禁 | 0 errors /41 warnings，50项任务未勾；不能作为功能PASS |
| 已存真实本机来源join | 只读逐项比较SSRC/RTP timestamp/payload SHA一致，7个processed部分对应4个不同编码包，范围全部在对应decoded区间内 |

日志见`stage-review/r86-independent/`。研发保存的正式RTC两次浏览器结果分别1通过7.9s、1通过8.0s，评审未重复运行。第二次原生captureTime同包对应有实际JSON；Final真实停止/重答仍由其现有正式断言/回执/历史证明。真实证据使用ASR/LLM/TTS/Jev本机替身，属于local-real RTC/浏览器/存储，不是external-real。

最后SSRC拒绝补丁晚于浏览器记录，报告已明确该时序；本次最终16项独立覆盖拒绝分支。不能把旧浏览器正路当最终跨SSRC补丁的真实重连验证。无厂商调用，原冻结原型不变。

## 仍阻塞的范围与最小下一步

1. **尚非RTC E2E**：目前captureTime是sender worker原生报告，未与服务器建立认证因果锚，未有严格processed样本回填、VAD候选源边界冻结或RTC E2E持久化。不能直接把worker/window/server时刻相减，也不能把四包join外推到整会话。现有`source_end_clock_unavailable`必须保持。
2. 下一步只需在同一worker接已有认证capture-clock挑战，明确同包captureTime与采样锚的时钟域及边界；回填仅接受连接/SSRC/RTP/hash完全证明的范围，缺包、断流或时钟失效保持缺失。接到既有候选冻结后，在原正式入口检查原轮次Final与API重启范围证据，才可关闭RTC指标。
3. jitter丢包/重连/手机/Safari、sender变换附加延迟、物理ADC/出声/AEC、真实完整模型场景及容量仍未验证。正式采用保留D-068用户决定，不自行替换默认链、不扩大架构。

本次产品决定：**无新增需求**。工程缺口按上述顺序关闭，不因当前结果再申请重复收费或重跑已通过的同例。

## 输入冻结边界

本次审查工作区r86源码与已保存证据，r86新包尚待研发在本报告后封装；未覆盖r85包，也不拿r85 hash证明新增代码。完整自测和最终独立验收仍须在候选范围收敛后执行。
