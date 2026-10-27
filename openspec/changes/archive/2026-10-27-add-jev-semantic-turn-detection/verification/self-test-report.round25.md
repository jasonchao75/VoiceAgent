# 研发自测报告 — 第二十五轮完整后端回归

**IN PROGRESS / NOT READY FOR INDEPENDENT REVIEW。** 本轮未修改生产代码。上一轮来源身份修复见[self-test-report.round24.md](self-test-report.round24.md)。

- 合并前轮安全切尾与数值来源身份修复后的完整后端：**591 passed，3依赖弃用警告，32.67秒**；无失败。日志见[backend-full.txt](development-20261022-r25/backend-full.txt)。前端任务播放/历史单测4项通过。原型SHA-256与D-048冻结值一致。
- D-052最小取消结论：保留原Opus/RTP音轨、麦克风及信令；取消旧生成并拒绝迟到输出，额外清除锁定SDK RawAudioTrack待发PCM。服务端清队列不是客户端停止回执。r19实际SDK测试与r20正式浏览器合成440/880Hz实验分别证明队列清理及旧答截短/新答接续，不证明弱网零尾音或硬件精确时间。说明见[当前方案](webrtc-cancellation-status.md)。
- 本轮未调用Jev/ASR/TTS真实API、未读取或输出密钥、未新增费用；未运行新一轮浏览器网络测试，浏览器证据仍为r20本地fixture厂商替身。

仍未完成：未知范围/混合缺时间快照完整恢复及重连时钟；真实六模型与厂商兼容；RTC编号缓存串行组合与精确任务回执；精确历史指标；完整UI状态/视觉/可访问性；弱网/真实手机/实机AEC。完整后端通过不能替代这些验证。无新增产品问题。未独立审核、未User Gate 2、未提交/推送/部署/归档或合并主规格。

测试产物：本轮日志位于development-20261022-r25；临时原始日志/tmp/jev-current-backend.txt及/tmp/jev-current-gate.txt；先前隔离数据/tmp/voiceagent-td-r15及忽略的NLTK资源保留，均不作为生产数据提交。
