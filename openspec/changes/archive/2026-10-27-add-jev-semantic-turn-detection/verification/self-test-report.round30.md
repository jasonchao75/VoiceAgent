# 研发自测报告 — 第三十轮六模型已知身份范围错误恢复

**IN PROGRESS / NOT READY FOR INDEPENDENT REVIEW。** 本轮不改变冻结原型、UI、依赖或媒体架构。

- 六模型已有可靠身份的非法范围，在校验时间前保留来源身份；时间倒序等异常保留epoch+ID缺口，后续其他来源不能掩盖。只有同epoch、同来源补回可靠范围才恢复提交。多行整帧失败回滚revision缓存，不能误清此前或其他行缺口。
- 修复Nova缺duration被默认0的问题。duration缺失保持未知，不伪造零时长范围；同start恢复可靠duration后沿用普通TD唯一提交权。
- 四家非法范围目标先红、既有缺范围场景仍绿；再扩展两种Flux及Nova，Nova缺duration目标先红。最终六模型×缺时间/非法时间加原子缓存等相关 **80 passed / 2.09秒、1依赖弃用警告**。完整后端 **611 passed / 34.56秒，3依赖弃用警告**，见[backend-full.txt](development-20261022-r30/backend-full.txt)。ruff/相关mypy通过；过程中的两行长度错误已修复。此为fixture/SDK证据，不证明真实厂商兼容。
- 测试映射和恢复证据已追加appendices/asr-event-mapping.md，保留现有材料与官方资料。未读取/输出Key或调用真实/收费API。

仍未闭环：完全未知身份/起点、跨连接时钟与旧缺口恢复；真实六模型时间覆盖；RTC编号缓存串行组合与精确任务回执；精确历史指标；完整UI状态/视觉/可访问性；真实弱网/手机/实机AEC。不能标记M1—M5全部完成或提交独立审核。未自填独立PASS/Gate 2、未提交/推送/部署/主规格合并/归档。

本轮保留Change内测试日志和/tmp/jev-r30-gate-before.txt；原/tmp/voiceagent-td-r15隔离数据、前轮临时日志及忽略的NLTK资源保持原状，未启动新服务。
