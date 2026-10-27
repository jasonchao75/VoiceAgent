# r97：D085真实TTS＋正式浏览器证据独立核查

2026-10-26，限定只读；没有执行API、浏览器、Docker、行为测试或授权重放。

**限定结论：现有证据支持本批真实TTS取消与正式WS浏览器播放组合通过，未发现新增确认阻塞。全产品仍为 INSUFFICIENT EVIDENCE；不签全Change PASS、Checkpoint C或User Gate2。**

## 核对结果

- D085的确认原话、call_d748adb0a44f4fea9ea2d5958ea926c8 item0、接收方、196字符、1连接/2Speak、30秒/ACK2秒和USD0.02预算与冻结计划相符。独立重算规范JSON request SHA256为`8cfd5bd5465d747373e6d81bf10dbdc513198e026dec9badbfc962c3aae7eb56`。delivery.external_calls记录confirmed/completed，执行日志含claimed_no_replay；授权已消费。
- r97 source-sha三项逐文件匹配当前输入，并与r96预检hash完全一致；production-source-sha八项也匹配。保留r96修复后的身份验证及失败停批保护，不把此前有缺陷的夹具当执行输入。
- probe-state与独占执行副本相符：实际1会话/1连接/2Speak，控制顺序Speak→Flush→Interrupt→Speak→Flush；匹配旧身份的SpeechInterrupted后才放行新Speak，两个SpeechStarted身份哈希不同，old_terminal=false。141792网络音频字节仅说明接收量，不能当播放量。身份匹配结论依赖已核hash执行器的fail-closed guard与ok记录，脱敏日志没有原speech_id供再次逐字比对。
- history实际一次td_commit、一次response_restart，旧1:1/新1:2对应不同playback_id。四条回执均204、audio_worklet_render、同一非空24kHz render_clock：旧started128→stopped2624样本，新started128→finished51840样本；旧回答没有以finished冒充停止。历史与receipts的任务、帧及样本值一致。正式页面实际渲染证据支持取消旧答后播放新答，并非SDK输出即播放的推断。
- 同时钟帧差`(96896−79872)/24000×1000 = 709.333…ms`。仅该次旧停止到新开播间隔；不是新增链路开销、全链精确延迟、P95或扬声器声学证明。保存的单例10.1秒通过记录无需收费重跑。

## 边界与下一步

USD0.00882为完整文本常规估算，实扣未知、没有厂商硬封顶。ASR/VAD/Jev/LLM仍为本地替身；RTC默认关闭。真实LLM工具依D086“先保留未验证”，不是最终范围排除或风险接受。手机/Safari、弱网、声学双讲、RTC真实厂商取消、多场景修订/重连、容量和成对新增延迟不能由此单例关闭。

临时Python3.11没有加载既有NLTK资源的原警告应保留；指定项目.venv/nltk_data后离线两句分割成功只支持环境定位，不代表真实LLM文本效果或原运行无警告。临时资源在/tmp/td-r97-D085，原始独占厂商日志为忽略文件，本审查未操作这些服务。

本次无需新增用户决定。后续按尚未验证矩阵推进；需要外部调用时另行精确授权，不重放D084/D085。
