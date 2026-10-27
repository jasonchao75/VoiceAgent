# r53 D-064：保留RTP有限候选的前置关口

2026-10-24用户原话“A好的，就用A吧”确认D-064，Q-046关闭。允许隔离有限候选，不是正式播放器替换/数据通道音频/收费授权。正常正式路由没有选择本模块。

## 实际闭合的链

MappedRawAudioTrack沿用锁定SDK 10ms队列/PCM/时钟/静音，只在实际recv取出数据时绑定不可变任务；取消未发队列同步移除身份，其他任务取消不记为音频输出。MappedOpusEncoder沿原resampler/codec记录实际packet PTS/duration和hash；native aiortc序列化后的RTP时间戳/SSRC/payload必须一致，跨包和32bit回绕保留坐标。控制通道只有样本范围/hash，无音频。

Chromium接收编码帧以实际SSRC/RTP timestamp和payload hash对应sidecar；独立WebCodecs Opus解码的输出timestamp/48000Hz/帧长必须匹配，再按多任务区间送既有td-audio-worklet。原生audio只作muted拉流sink；唯一可听输出来自现有Worklet。priming=-312由实际编码PTS记录，不是固定延迟猜值。跨界包保留A/B范围，不要求有损输出逐样本恢复源PCM相等。

审查补齐异步hash→有状态解码的有序单泵，来源时钟缺口拒绝；packet/mapping/decode等待1秒及队列限制仅为有限候选上限，不是批准的正式产品默认参数。失败发mapping_failed并中断任务播放器，不伪报开播/完成。

## 证据及边界

mapping-red.txt为模块缺失collection error，不能称3个独立业务红灯。mapping-green.txt三项通过/0.95秒：原生队列取消/静音、混合包/时间戳回绕、payload/时钟拒绝。browser.txt首次仅因旧Vite未运行，未执行业务，不算映射失败；启动自有本地服务后browser-mapping-attempt.txt一项通过，再补有序解码/负例的browser-final.txt两项通过/1.4秒。正常browser-mapping.json中A/B各1440个实际Worklet渲染样本；browser-rejected.json篡改hash被拒，无开始/完成及PCM。mapping-summary.json区分control/hash等待和未测E2E延迟；绝不将几毫秒等待说成新增端到端延迟。最初mypy optional类型错误已修，types-final.txt通过；ruff和node语法通过。

未接正式mobile-demo、现有SerialAudioOutput/IdentifierOutput尚未绑定此候选，Final/编号组合NOT_RUN。手机/Safari/弱网、PLC/丢包恢复、CPU/新增端到端延迟、听感未测。只证明此本地有限链；不签整体R1、Checkpoint或采用决定。

## 复现和下一项

根目录：PYTHONPATH=. .venv/bin/python -m uvicorn td_rtp_candidate_app:app --app-dir tests/ui --host 127.0.0.1 --port 8791。frontend启动现有Vite127.0.0.1:5177（不另造产品验收页）。frontend执行VOICE_AGENT_UI_URL=http://127.0.0.1:5177 VOICE_AGENT_TD_RTP_CANDIDATE=1 VOICE_AGENT_TD_UI_EVIDENCE=../test-results/td-rtp-candidate npx playwright test tests/ui/td-rtp-candidate.spec.js --project desktop-chromium。测试所有产品API拦截，不用Key；唯一音频为fixture本地生成30ms×2合成音，ICE无STUN，native RTP传音频。源文件hash单列，代码未提交；原r48归档副本未覆盖。本轮自有服务会话32958/1692、端口8791/5177及被忽略test-results失败trace保留，源码/日志证据在本目录，无额外磁盘录音。

下一步沿同一候选接SerialAudioOutput/真实回执闭环，做Final取消旧任务和编号跟读→提问→清空/迟到组合；关口不能证明则停止报告，不追加泛用探针。成功后先报告延迟/兼容风险，正式采用仍待用户决定。ASR/TTS旧授权不重放。
