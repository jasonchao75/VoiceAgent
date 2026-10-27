# D-054一次本地RTC可行性前置关口

结果：**NOT PROVEN / STOP**，不是正式组合验证通过。

执行：`PYTHONPATH=. .venv/bin/python /tmp/rtc_r39_probe.py`（归档源为本目录rtc_task_mapping_probe.py，复现时以仓库根目录执行）。进程0只表示诊断采集完成，JSON gate=NO_GO_TASK_MAPPING_NOT_PROVEN才是验收结论。

实际使用锁定Pipecat SmallWebRTCClient.write_audio_frame、RawAudioTrack、aiortc RTCRtpSender._run_rtp及Opus编码器；只把DTLS发送口换为进程内序列化包收集，无socket/浏览器/厂商/真实Key。输入是各30ms的A/B两任务测试PCM（非可听语音质量测试）；记录11个10ms来源帧和5个真实序列化RTP包。

关键观测：第一包在输入pts=480/24k时发出；第二包相对RTP=960/48k、触发输入pts=960/24k。仅按输入名义时间覆盖，第二个20ms区间横跨30ms任务边界；第三包触发时输入已为自动静音，但名义区间仍与任务B重叠。因此“用当前输入的任务ID给发出的包贴单一标签”不成立。名义覆盖仅为测试oracle，不是实际解码后的样本归属；编码延迟/滤波/解码状态尚未证明，**不输出伪造的逐任务开播/停止**。JSON里的任务跨度由测试输入已知时长派生，不能当接收端测量。

此实验没有实现候选的RTP范围sidecar、客户端解码/Worklet桥；故只能报告前置关键条件未证明，不能断言保留RTP的所有候选均不可行。按D-054停止，不继续浏览器能力探测，也不执行依赖任务身份的Final取消/编号仲裁组合。原r20取消结论不变，未改正式播放链。

延迟影响：未测量新播放链；仅知现有Opus20ms分帧和跨帧缓冲，不能把20ms说成新增端到端延迟。兼容性：未验证新链的任何浏览器/手机，原Chromium能力探测不等于完整兼容。
