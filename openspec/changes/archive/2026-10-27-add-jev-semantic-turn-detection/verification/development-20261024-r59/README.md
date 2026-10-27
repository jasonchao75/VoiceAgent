# r59：D-067隔离保留RTP候选三个实际关口通过

## 本批边界与结论

2026-10-24用户call_b582248f1f024c22a6c81199cc2dfcac第0项“允许这批本地修复确认（推荐）”，D-067先登记、Change门禁独立返回0，确认源码与r58的14个文件hash无变化，再以claim.json独占登记开始。只三条本机连接，无重试/厂商/Key/费用。先1秒源映射关口通过（mapping-gate.txt返回0）才运行两个serial组合（serial.txt返回0），源码没有现场修补后偷偷重跑。source服务端硬限分别1/2/2秒，实际服务完成后Ctrl-C停止（会话85186）。Vite5177自有前端保留供审阅，没有候选服务继续发音频。

映射关口覆盖旧source_start12168，实际经过逐包decode+flush持续解码，不以AudioData微秒标签当任务身份，A/B各1440样本对应不丢不重。Final场景实际old task_started128、task_stopped256，再new task_started和task_finished14880；capture接受真实render clock，serial派发新答严格晚于旧终态接收，用户提交数1、重复Final不重启/成功工具不重放。编号场景真实IdentifierOutput/EchoAudio永久缓存/collection/rules：续说后echo仍playing、question queued、stop_requests空；clear结果cleared/generation1，echo stop256后Q完整14880，串行槽未按发送结束提前放行。

结果：mapping-gate.txt 1passed/2.1秒，serial.txt 2passed/2.2秒。这是三个有限本地实际关口通过，不是完整R1或正式默认播放器采用。旧r54失败不删除/改写。JSON保留实际任务/源区间/hash/回执与状态顺序，不包含PCM或凭证。

## 延迟：可算与不可算

combination-summary.json的decode_job_ms是同worker performance时钟下单包decode+flush实际耗时，包含API排空调度，不是总E2E、手机/目标CPU统计。Final本地27包中位约0.1ms、最大约0.3ms；编号22包中位约0.2ms、最大约0.5ms。具体原始值见JSON，不把短流计时精度当无限精度。

同一AudioWorklet时钟下Final旧stop到新start间隙16ms，编号clear旧stop到Q start约37.33ms。这是本次合成场景衔接间隙，不是用户开口到回答的延迟，也不是相对原生播放器新增16ms/37ms。**没有同输入原链对照，新增E2E延迟尚未量化**；不能据包级数据宣布零额外成本或体验合格。

## 尚未完成的正式接入与风险

此结果来自隔离fixture把现有SerialAudioOutput/IdentifierOutput/CallCapture接原生SDK队列、aiortc/Opus/RTP、Chromium worker/WebCodecs与既有AudioWorklet；没有把mobile-demo正式路由、SmallWebRTC客户端输出和已鉴权API接入，不能把fixture收到回执称正式发布入口通过。r58源码副本就是本批运行版本，未改生产默认开关。

手机/Safari/API缺失、弱网/丢包/重连/PLC、跨包Opus波形听感、物理设备/AEC、目标1核1GB容量仍未验证。浏览器需RTCRtpScriptTransform与WebCodecs音频解码，不能承诺所有移动端支持；遇不明对应当前候选明确失败，不静默猜时长。正式启用前需明确采用范围及回退，不批准新服务端AEC或数据通道音频。

## 后续交付条件

本批授权已用完，不能追加原链对照或正式入口通话。应先给用户本结论/延迟边界/风险，再决定是否让候选进入受控开发环境的正式入口接入与后续验证；正式默认替换仍无授权。ASR旧固定数据缺失、TTS仅one真实成功等H2与完整UI/历史/最终回归仍沿阶段报告，不自行缩范围，不填独立PASS/C/Gate2。

必要复现需新授权；命令分别为td-rtp-repair-gate.spec.js与td-rtp-serial.spec.js，均workers1/retries0/max-failures1，必须先读首关口退出码，不能整批重放D-067。当前所有原始源/版本以r58源码指纹/副本及原阶段snapshot为准。本次新临时td-rtp-cache-*由fixture保存合成单元，属于测试资源，未提交或删除用户内容；忽略test-results保留派生日志。
