# 研发自测报告 — 第三十三轮六模型配置与来源草稿隔离

**IN PROGRESS / NOT READY FOR INDEPENDENT REVIEW。** 本轮只补/纠正测试和交付记录，未改生产代码或冻结原型。

- 纠正范围恢复回归的Soniox/Assembly模型ID标注；先加入正式Catalog校验，旧ID4项场景失败，再改为目标stt-rt-v5/universal-3-5-pro。历史日志不改写，证据边界见[更正说明](asr-model-evidence-correction.md)。不能把旧IDfixture当作目标型号或真实兼容。
- 六模型配置/会话深复制冻结、凭证不入快照、source能力与既有范围行为 **89 passed / 2.13秒，1依赖弃用警告**；ruff通过。
- 正式Bot settings→ASR抽屉切provider_native→Advanced隐藏TD入口且General可访问→切回self_developed恢复未保存650ms草稿，桌面与窄屏 **2 passed / 5.4秒**。初次窄屏测试未收起现有抽屉、导航被覆盖而超时；查看实际截图后补正常收起步骤，不用force、不改视觉或产品流程。失败与最终日志均保留。
- [证据目录](development-20261022-r33/)。M1-1配置/来源/会话隔离及草稿保留具备实现与本地/离线证据；M1-2/3来源归属与重连仍未完成。未运行本轮新全量，最近r32全后端616项+之后定向70项的范围不扩大。

仍未闭环：完全未知ASR身份/起点、跨连接时钟与旧缺口恢复；RTC编号缓存串行组合/精确回执；精确历史指标；完整UI状态/视觉/可访问性；真实六模型/Jev/TTS/弱网/手机/实机AEC和目标容量。当前不提交独立审核、不自填PASS/Gate 2；无外部真实/付费调用、提交/推送/部署/主规格合并/归档。

本轮Vite仅本机5175，用fixture拦截API，验证后停止。日志保留Change内；浏览器失败trace/screenshot位于忽略的test-results/playwright，正式截图沿用r9证据目录，未改冻结基线。/tmp/jev-r33-gate-before.txt与先前隔离/tmp数据及忽略的NLTK资源保留。
