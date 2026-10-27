# 研发自测报告 — 正式浏览器本地网络增量

**IN PROGRESS / NOT READY FOR INDEPENDENT REVIEW。** 完整M1—M5及UI A/B未闭环，不申请独立审核或Gate2。前轮详见[self-test-report.round13.md](self-test-report.round13.md)。

- 新增仅loopback、/tmp隔离存储的本地测试应用：保留正式UI/API/数据库/WS/SDK，替换外部ASR/Jev/LLM/TTS与VAD推理，阻断非loopback连接。没有另外制作验收页面。测试创建数据前先检查专用health标记；首轮替代registry遗漏health属性导致500，修复后通过，失败日志保留。
- Chromium使用假麦克风产生实际上行；正式页面创建保存Bot、启动真实本地WebSocket、解码任务PCM并在实际AudioWorklet产出回执，经正式认证API写入历史。Partial已开播后Final取消旧回答，收到真实停播回执后才播放新回答；普通提交数仍为1，刷新后历史保留两版回答。
- 新增端到端本地网络用例 **1 passed，6.6秒**：[browser-network-second](development-20261022-r14/browser-network-second.txt)。这里的端到端仅指本地正式通路，所有推理及VAD输入判断均为确定性替代；不证明真实模型效果或物理麦克风/AEC。后端最近完整574项、前轮浏览器组件6项结果仍见r13；本轮没有改生产处理代码。
- 用户明确Jev地址/Key尚未准备；已只读核查[官方接入入口](jev-access.md)，没有账户/凭证/费用操作。真实厂商联调需要有效配置，并另批授权数据、厂商、费用上限与停止条件。

仍未完成：WebRTC任务/实际渲染映射；精确渲染时钟/真实指标；未知ASR范围/重连与真实六模型；完整UI A/B（中英、缓存失败/试听、真实API刷新重启及视觉/可访问性矩阵）；真实厂商及实机耳机/外放双讲。不得据本地通路通过声称这些范围通过。

本地服务已停止，隔离数据保留/tmp/voiceagent-td-r14（仅测试虚构文本、虚构测试Key与假麦克风录音/缓存）；不提交这些数据。原型v0.14未改；未填独立PASS/Gate2，未提交/推送/部署、合并主规格或归档。
