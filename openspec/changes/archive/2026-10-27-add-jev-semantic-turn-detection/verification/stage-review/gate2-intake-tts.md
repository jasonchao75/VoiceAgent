# Gate 2 接收复核：Flux TTS 取消边界与 r97 证据

- 日期：2026-10-26
- 角色：独立审核子 Agent；不修改生产实现，不执行外部调用。
- 范围：r94–r97 涉及的 Flux TTS 取消修复、响应身份隔离及 r97 正式 WS 页面证据。
- 结论：本轮范围内未发现新增确认缺陷。取消修复可以作为后续 Gate 2 复验的基础；本报告不代表整个 Change 或 User Gate 2 通过。

## 独立检查内容

直接阅读 `src/tts/confirmed_flux.py`、`src/tts/scoped.py`、`src/tts/response_scope.py`、本地安装的 Pipecat Flux TTS 与 TTS base 实现、取消边界测试，以及 r96/r97 原始证据。没有把研发或此前独立报告的结论当作实现正确性的依据。

当前取消流程具备以下保护：

1. 发送 Interrupt 不阻塞本地停止流程；同一待确认边界只发送一次。
2. 确认前丢弃旧 PCM 和旧 SpeechMetadata，防止没有任务身份的厂商音频被标成新的回答。
3. 新 Speak 等待原取消截止时间；超时或错误后禁止继续发新语音，迟到确认不能恢复失败边界。
4. 发送任务按代次隔离；旧发送失败不能污染新一代取消，清理会取消并等待所有发送任务结束。
5. 响应作用域在音频进入队列及发出时均校验；上下文复用时生成新的身份，防止迟到音频被重新归属。

这些保护与已安装 SDK 的实际处理方式相符：该传输的 PCM 本身没有 speech ID，基础实现会关联当前音频上下文，因此确认前的隔离确有必要。

## 本轮独立离线验证

运行：

```sh
.venv/bin/python -m pytest -q tests/test_flux_interrupt_boundary.py tests/test_td_tts_scope.py tests/test_td_tts_cancel_probe.py tests/test_td_tts_browser_fixture.py tests/test_td_serial_output.py tests/test_td_response_revision.py
```

结果：**35 passed，2 个弃用警告，1.14 秒**。测试使用本地替身，不连接厂商。警告涉及 Pipecat AudioContextTTSService 和 WorkerRunner 既有接口弃用，不是本次测试失败。

门禁：`python3 scripts/quality/verify_change.py add-jev-semantic-turn-detection` 返回 **PASS，0 errors / 37 warnings，8 项任务未勾选**。门禁通过不等于这些剩余项目已验收。

将当前文件与 r97 `production-source-sha.json` 比较，记录的 8 个生产文件 SHA-256 全部一致，覆盖 TTS、pipeline、API、前端页面、播放控制器及 AudioWorklet。

## r97 原始证据核对

已读取 `development-20261026-r97/README.md`、`result-summary.json`、`D085/receipts.json` 和 `D085/probe-state.json`。

- 厂商侧记录 1 次连接、2 次 Speak；顺序为旧 Speak/Flush、Interrupt、新 Speak/Flush。收到 SpeechInterrupted，且旧任务在取消前没有正常终结。
- 浏览器四条回执分别为旧任务开始、旧任务停止、新任务开始、新任务结束，均返回 HTTP 204；没有把旧任务伪报为正常播放完毕。
- 回执来自 `audio_worklet_render`，使用同一个 24 kHz render clock。旧停止 frame 79872，新开始 frame 96896，相差 **709.333 ms**。
- 这证明该单次 WS 浏览器样例中，播放器处理了停止并随后渲染新任务；不证明扬声器真实出声，也不能将该差值解释为新增延迟或 P95。
- 本轮没有重跑 D-085。该授权已经消费；r97 真实 TTS 记录仅作为既有外部证据审阅。

## 未验证边界与后续建议

1. r97 的 ASR、VAD、Jev、LLM 由本地替身提供，不能作为完整真实语音链路或真实 LLM 工具行为通过的证据。D-086 暂缓项仍由总审核保留。
2. 本轮没有重跑正式浏览器；根审核可使用 r96 wire 模式和独立临时目录复验正式页面、回执及失败停止，不能复用已消费的外部调用授权。
3. 本报告不覆盖 RTC、手机、弱网、物理扬声器/AEC 或真人双讲；无麦克风环境的渲染回执不能替代这些验证。
4. 当前没有需要用户重新决策的新增 TTS 产品问题，也没有生产修复建议。先完成总审核的其余范围，再决定 User Gate 2 是否可提交。

## 产物

本轮新增本报告；离线 pytest 未主动创建录音、数据库或外部请求日志。未修改生产代码、测试代码、冻结原型或交付状态文件；现有测试缓存不作为交付证据提交。
