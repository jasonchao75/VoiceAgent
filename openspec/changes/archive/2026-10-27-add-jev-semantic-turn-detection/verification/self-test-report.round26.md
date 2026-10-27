# 研发自测报告 — 第二十六轮归一化原子性修复

**IN PROGRESS / NOT READY FOR INDEPENDENT REVIEW。** 最近完整后端591项通过见[self-test-report.round25.md](self-test-report.round25.md)；本轮修改后未重跑全后端。

- 修复Speechmatics/Soniox多片段快照的内部缓存污染：前面的正常片段先写入revision缓存，后续非法时间导致整帧返回空；之后相同正常片段被误判重复、ledger永远收不到。现在拒绝整帧时恢复此前不可变SourceSegment缓存，未返回的数据不消耗revision。
- 两家缺行为回归先红；修复后增加首次出现/已有片段修订两种状态。相关ASR/ledger/控制器/实际SDK编号管线 **64 passed，1依赖弃用警告**；ruff、相关mypy通过。证据见[本轮目录](development-20261022-r26/)。
- 此修复只保证失败归一化不会吞掉后续重发片段，不证明混合未知时间快照能够完整归属、恢复或提交。无新产品决定、无真实厂商或付费调用。

剩余未闭环：未知范围/混合缺时间快照/重连时钟；真实六模型/厂商兼容；RTC编号缓存串行组合与精确任务回执；精确历史指标；完整UI状态/视觉/可访问性；真实弱网/手机/实机AEC。不得提交独立审核或标记Gate 2通过。无提交、推送、部署、主规格合并或归档。

本轮仅保留Change内测试证据；原/tmp/voiceagent-td-r15隔离数据、前轮临时日志与忽略的NLTK资源保持原状。

更正：r26初次门禁因新增问题记录缺summary字段而失败，后续格式检查的成功不能覆盖该失败；已补齐字段并单独重跑，结果见development-20261022-r27/gate-schema-repair.txt。
