# 研发自测报告 — 第十六轮窄屏与媒体路径核查

**IN PROGRESS / NOT READY FOR INDEPENDENT REVIEW。** 原范围未缩减；M1—M5/UI A/B未闭环。此前本地网络、缓存/发布、失败恢复、重启及跨Bot隔离证据见[self-test-report.round15.md](self-test-report.round15.md)。

- 正式路由390px、实际本地API读取/保存通过，根页面与浮层/TD容器没有横向溢出。实际截图进一步发现Gap数值可用宽度仅21px，三位数字加步进器至少需要45.625px；新增断言先红后绿，调整间距字段内边距及窄屏列宽后通过。未修改冻结原型。最新1 passed / 1.4秒，构建及diff空白检查通过。[证据与截图](development-20261022-r16/)。截图是正式页面含隔离库Bot列表，不是独立验收壳；不代表完整视觉比对已完成。
- WebRTC连续RTP通路缺本Change逐任务实际渲染/停止映射，SerialAudioOutput/缓存跟读当前仅挂WS。新增[工程取舍证据](development-20261022-r16/webrtc-playback-gap.md)，Q-042已询问媒体架构选择；确认前不改受影响架构、不声称RTC支持。
- 没有使用.env真实Key或调用外部推理。隔离测试服务继续使用8765/5174，/tmp/voiceagent-td-r15保留测试库/假凭证/合成音频；真实.env不打印、不提交。

未闭环：Q-042/WebRTC任务映射；精确渲染时钟与指标；未知ASR范围/重连及真实六模型；完整UI中英/状态/可访问性/视觉矩阵；真实厂商和实机/AEC。没有独立审核PASS/User Gate2，未提交、推送、部署、合并规格或归档。

追加矩阵：正式配置/历史/渲染/本地网络在桌面与窄屏项目24 passed / 28.8秒；2项重启协调用例按设计跳过，单独重启证据在r15。ui-checklist首页及正式证据区已纠正为A/B部分进行中，原型历史记录不冒充正式实现。证据browser-matrix.txt。

本轮后端全量重跑574 passed / 33.45秒，3条依赖弃用警告，backend-full.txt。不得以全量绿色替代真实厂商/WebRTC/精确指标/完整UI的缺失证据。

追加缓存失败恢复：正式页面注入生成API 503，保持配置/缺缓存/未发布状态，按钮恢复可重试；显式重试实际本地API完成音频准备且不自动发布。桌面和窄屏2 passed / 2.0秒，cache-failure-recovery.txt。生成音频仍是本地合成fixture；未调用真实TTS。同步修正清单里已过期的“仅原型/完整WS网络未接”描述，保留具体未验证边界。
