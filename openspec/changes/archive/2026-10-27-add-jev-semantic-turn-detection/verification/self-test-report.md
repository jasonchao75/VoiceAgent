# r95当前真实TTS专项

D084获本批授权后唯一执行成功：1连接2Speak、实际SpeechInterrupted、19200字节在途旧PCM与取消后旧输出0，新响应49920样本；不同speech身份与协议顺序匹配。证据development-20261026-r95。源码与r94冻结SHA一致，未重复不受影响的773后端/类型/前端检查。

实扣账单未知；未验证浏览器/物理实际停播、RTC及ASR/Jev/LLM整链/延迟分布/其他voice。196字符授权已消费不可重放；LLM按用户选择暂缓，不签完整C/Gate2。

# r94当前实现与自测

Flux取消确认屏障、旧音/旧Metadata隔离、本地控制不等网络发送，以及全部sender任务/代次清理已修；原独立复现转绿并支持关闭。当前完整Python3.11后端773通过/9可选Docker未开启/10依赖警告/37.71秒，mypy79源和Ruff通过。证据development-20261026-r94，限定复审stage-review/repair-review-r94.md。

真实取消批次精确196字符/1连接2Speak/30秒/US$0.02等待专属授权，尚未调用；不能以“先做TTS”替费用批准。厂商真实取消/实际客户端停播、资源新版本/硬件/完整性能仍未验证，LLM按用户指示暂缓；C/Gate2不签。

# r93当前资源与Docker语义纠正

D083允许启动本机Docker并准备隔离测试。真实Docker语义证伪r92“原四输入缺项”：父目录!规则其实过宽，旧Gitwildmatch审计不适用；结论已撤回并保留历史。改具体白名单后原生9项通过，真实标准镜像构建成功；1CPU/1GiB真实Silero及正式WS限定资源结果见development-20261026-r93/README.md（本轮独立限定核对另见stage-review/evidence-review-r93.md）。没有实际前端.env文件/Key外泄证据，未推送镜像。

# r92 当前真实Jev专项增量

D082已授权并消费：Jev1.14两请求，融合等待963→1952.5ms；已留存ASR事件回放＋生产normalizer/coordinator与受控音频时钟，旧Final7163点0提交、原Tmax8500点1提交。不等于实时ASR/Jev或新增链路延迟；未采新目标7952.5点。4项执行器离线红绿及Ruff通过，证据[本轮报告](development-20261026-r92/README.md)，限定独立审查见stage-review/evidence-review-r92.md。

另修Docker上下文遗漏三个页面入口及一个COPY脚本，四项静态锚定规则审计红绿通过；Docker镜像尚未构建，1核1GB/设备/实时完整效果仍未验证。等待用户选择是否启动本机Docker或提供隔离Linux。无src/前端或冻结基线变化，RTC候选默认关闭，未部署或签C/Gate2。

# r91 当前目标解释器增量

实际隔离Python3.11.15＋锁定依赖：pip check通过，756后端通过（9依赖警告、67.20秒），mypy3.11目标79源通过；旧类型环境限制关闭。证据与复现见[本轮报告](development-20261026-r91/README.md)。无生产代码/原型/默认RTC变更，无厂商调用。

D081新ASR否定/续说已授权并消费：1连接11.74秒、26事件范围完整，真实Partial test→cancel改写、Final保留not和续说；仅ASR/normalizer路径，无Jev/LLM/TTS。实扣费用未知，不复用本批授权。目标Linux1核1GB的本地Docker daemon不可达；手机/Safari/VoiceOver/弱网/声学AEC、完整厂商效果及新增延迟仍未验证。完整C/Gate2未通过。

# r90 当前自测增量

r89唯一新增词表表头缺陷已修；本地键盘又发现并修复焦点缺陷。Chromium表头6/键盘10、Google Chrome组合14与构建通过；红绿、正式截图、版本与复现见[本轮报告](development-20261026-r90/README.md)。未重复无变化756后端/25客户端，原六项独立关闭保持。

真实专项未执行：分别见[厂商计划](vendor-specialist-test-plan.md)及[设备性能计划](device-performance-test-plan.md)。费用批次待精确素材/hash/预算冻结后新授权；旧授权全部已消费。本轮无外部调用、无架构/默认RTC改变、无部署。独立增量复审另见stage-review/repair-review-r90.md；不签全ChangePASS/C/Gate2。

# 研发自测报告 r89（2026-10-26）

**当前：实现与自测包已交独立复审；原六项返修及RTC来源覆盖缺陷已复审支持关闭。不是全Change独立PASS/C/User Gate2。**

完整当前结果、红绿、版本、复现、临时数据与回退见[r89交付报告](development-20261026-r89/README.md)，[22项场景映射](current-scenario-matrix.md)，[交包要求逐项核对](development-20261026-r89/completion-audit.md)。旧报告原文保留[self-test-report-through-r88.md](self-test-report-through-r88.md)，不能当当前状态。

- 当前完整后端756 passed/5依赖警告/40.55秒，客户端25 passed；Ruff、实际Python3.13 mypy79源、Vite通过。
- 严格正式RTC冷启动及同进程第二通各通过，两响应有源样本/同包摘要/实际渲染双端锚与Final取消证据；两个完整历史进程重启后逐值一致，实际Sessions页1440/390展示/恢复/无溢出通过。
- 原r88 six fixes与实际回执响应丢失+错误遥测挂起故障、完整性禁用正式页面1440/390证据保留；无变化未重复扩测。独立结论见[返修r88](stage-review/repair-review-r88.md)、[来源修复r89](stage-review/repair-review-r89.md)。研发不覆盖审核意见。
- r88原失败native快照缺失，无法唯一历史归因；r89首探针错误/格式失败已纠正并留证，不以无效计数0归因生产。当前E2E仍为较宽保守区间，不声称精确性能。
- 未验证：物理声学/AEC/双讲、手机/Safari/弱网、跨连接可靠钟、目标1核1GB/Python3.11、完整真实厂商多语种/WPM/续说改写重连/取消/效果与新增延迟。错误遥测未送达时后端仅保留未知事实，不保证确定失败原因送达。
- 真实调用仅既有已消费逐批授权结果，详情delivery-status.external_calls和r85；本轮无费用/客户数据。RTC默认采用、独立完整C及User Gate2仍待相应决定/验收，不提交/推送/部署/归档。


## r96：正式浏览器混合TTS离线准备

[证据与复现](development-20261026-r96/README.md)：正式页面/API/实际SDK及AudioWorklet，厂商socket与ASR/Jev/LLM替身；单条浏览器组合通过，旧实际停止后同钟新开播。新夹具7项定向单测与Ruff通过；独立预检两处边界返修后，正常组合及故意失败清理各一次通过，两缺口已独立预检关闭。无外部调用，D084不复用。真实TTS浏览器组合未授权，物理声学/RTC不由此证明；不修改独立验收结论。


## r97：D085真实TTS正式浏览器单例

[证据/范围](development-20261026-r97/README.md)：1连接2Speak、固定196字符，正式页面旧实际开播→Final停止→新开播结束，真实厂商取消确认与同钟Worklet回执通过，1条Chromium10.1秒。费用实账未知，未重试。ASR/VAD/Jev/LLM替身，不代表RTC/物理声学/设备/完整真实链。无生产实现变更，待独立证据核查，不签Gate2。


## G2-02 编号未提交历史展示返修（2026-10-26）

证据[history-repair](gate2-intake/identifier/history-repair/README.md)。前端hasTurnContent保留实际编号/提醒/跟读轮次，不伪造普通提交或LLM指标。两个目标负例先失败，8项正式组件回归4.9秒通过；原满位/超位正式WS/认证/Worklet组合2项30.4秒通过，build及门禁通过。无真实厂商调用，待独立限定复审，非整体Gate2通过。

本缺陷已独立复审支持关闭，报告gate2-intake/identifier/history-repair/independent-review.md；此前“待复审”仅执行时点，不扩为整体验收通过。
