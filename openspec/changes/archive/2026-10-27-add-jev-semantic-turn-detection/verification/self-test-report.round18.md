# 研发自测报告 — 第十八轮语言增量及WebRTC方案确认

**IN PROGRESS / NOT READY FOR INDEPENDENT REVIEW。** 前轮完整后端574项及页面24项、本地缓存/持久化/重启证据见[self-test-report.round16.md](self-test-report.round16.md)。

- 复用冻结v0.14文案，在正式TD/Jev组件加入语言入口，默认中文；语言偏好只存浏览器，不进入Bot请求。用户输入、提示词、选项含义、样本和请求JSON不翻译。入口缺失先红后实现；设置/本地通话套件9 passed / 14.1秒（1重启协调跳过）；实际保存请求体切换前后相同、用户值保持、默认中文在桌面/窄屏4 passed / 3.4秒。构建及diff检查通过。证据development-20261022-r18/。
- 历史语言、动态标签/完整可访问性/视觉矩阵仍缺；不标完整UI A/B通过。原型字节未改。
- 用户已选择Q-042 A，记录D-051并同步Delta/design/tasks；WebRTC媒体桥尚未实现，此次仅产品决策闭环，不冒充运行验证。

未闭环：WebRTC任务媒体桥/弱网/移动；精确渲染时钟指标；未知ASR范围/重连及真实六模型；完整UI矩阵；真实厂商与实机AEC。无真实Key使用/付费调用/部署，无独立审核PASS/Gate2/提交/推送/主规格合并/归档。隔离服务8765/5174与/tmp/voiceagent-td-r15测试数据保留。

D-052取代D-051：用户要求先说明原音轨最小取消方案，A执行批准撤回；Delta中新增的数据通道强制要求已移除，design/tasks同步，WebRTC媒体代码未改。SDK队列本地实验定位cancel Future后100ms旧PCM仍可读；上层已有打断，不得推导RTP不能取消。分析见development-20261022-r18/webrtc-minimal-cancellation.md。浏览器网络残留/恢复与实机未验证。
