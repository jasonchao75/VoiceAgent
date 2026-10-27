# r97：D085真实TTS与正式浏览器组合

2026-10-26。限定研发单例通过，待独立证据核查；不签全产品PASS、C或Gate2。生产实现未改，使用r96独立预检修复后相同源码（source-sha.json）。

## 实际结果

D085授权call_d748adb0a44f4fea9ea2d5958ea926c8 item0，原话“授权本批（上限US$0.02）”。精确计划../deepgram-tts-formal-browser-r96-plan.json，hash8cfd5bd5465d747373e6d81bf10dbdc513198e026dec9badbfc962c3aae7eb56。仅api.deepgram.com/flux-alexis-en，196虚构英文字符，实际1连接2Speak、无重试/重连；未发录音或客户数据。ASR/VAD/Jev/LLM本地替身，无其真实外部调用。

正式 `/` 页面、原组件/SDK/认证回执/历史存储与AudioWorklet执行，Chromium单例10.1秒通过（总10.7秒）。旧1:1开播128样本，认证开播才放行固定Final；旧task_stopped2624样本；新1:2 start128、finished51840样本。全部回执204、页面错误0。一次td_commit/一次response_restart；无旧task_finished冒充停止。

真实厂商SpeechInterrupted已匹配旧身份（哈希），再允许新Speak；两个身份不同，旧SpeechMetadata在取消前未结束。厂商控制序列及总141792字节在probe-state中；不把全部网络字节当已播放。客户端同一24kHz render_clock，旧stop frame79872、新start96896，间隔709.33毫秒；仅这一次停旧到新开播观察值，包含厂商网络/合成/缓冲，不能称新增链路开销或P95。浏览器渲染非物理扬声器声学证明。

预算USD0.02，按完整文本常规价格估USD0.00882，实际账户实扣未知，无厂商硬封顶。D085已消费；不得再执行或复用D084/D085。

## 证据与复现边界

D085/history.json、receipts.json、probe-state.json、formal-page.png；D085-execution.jsonl为不含凭证的本批独占原日志副本，原本保存在scripts/vendor/deepgram/logs/deepgram-tts-formal-browser-r96-v1-D-085.log（忽略）。result-summary.json和source-sha.json为汇总/当前输入。运行Python3.11.15、Chromium153，正式现有dist。

实际命令是`python -m tests.ui.td_tts_browser_app --execute --authorization-decision D-085 --data-dir /tmp/td-r97-D085`，再在frontend用VOICE_AGENT_TD_TTS_BROWSER=1、VOICE_AGENT_TD_TTS_MODE=external、VOICE_AGENT_UI_URL=http://127.0.0.1:18996运行td-tts-browser.spec.js desktop-chromium retries0。本授权已用完，命令仅审计记录，不是重跑许可。离线复现用r96 README的wire模式和全新临时目录。临时库/密钥/录音仅/tmp/td-r97-D085，不提交；本批服务已退出，未操作旧Docker服务。

启动时NLTK尝试下载punkt_tab被既有安全校验拒绝，未放开代理/下载；该警告不影响本次固定文本通过，不据此宣称任意真实LLM文本分句兼容。

## 仍未验证与下一步

独立核对授权/hash/次数/SDK身份与浏览器历史证据；无需付费重跑。随后真实LLM工具仍缺用户指定厂商/模型/域名及独立单批授权（用户先做TTS取消）；手机/Safari、弱网、硬件双讲/AEC、RTC真实厂商取消、多场景/多语种ASR修订重连/WPM、真实负载及成对新增延迟另列矩阵，不由本单例关闭。保留RTP/RTC候选默认关闭，不新增服务器AEC。

NLTK环境定位补充：以`NLTK_DATA=/Volumes/work/OpenCode/VoiceAgent/.venv/nltk_data`仅离线运行同Python3.11，已找到tokenizers/punkt_tab/english，正确切分“This is a booking. This is the replacement answer.”为两句。没有下载、没有关闭安全开关，临时环境未来需显式加载；不重跑D085、不宣称原警告消失或真实LLM工具已通过。

D086补充：用户明确“先保留未验证。”，真实LLM工具专项暂缓，不猜测厂商/模型、不申请费用或发请求；这不是最终验收范围排除或风险接受。后续恢复需提供厂商/模型/域名，再单批授权。

运行版本补充：production-source-sha.json记录8个相关生产模块当前SHA，source-sha.json记录3个夹具输入；均只用于本次证据追溯，不是修改冻结原型或独立通过声明。

独立证据核查已完成：../stage-review/evidence-review-r97.md支持本批限定组合证据、未发现新增确认阻塞；全部Change仍INSUFFICIENT EVIDENCE。上文“待独立核查”为研发执行时点，当前以此结论为准。
