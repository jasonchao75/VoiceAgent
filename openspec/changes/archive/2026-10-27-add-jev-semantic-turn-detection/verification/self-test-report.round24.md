# 研发自测报告 — 第二十四轮来源时间身份修复

**IN PROGRESS / NOT READY FOR INDEPENDENT REVIEW。** 前轮范围证据/安全切尾及全后端证据见[self-test-report.round23.md](self-test-report.round23.md)。

- 修复Speechmatics/Nova将同数值时间的不同JSON数字格式当不同来源：0→0.0原先可把“1→12”修订追加成“112”。内部来源时间按实际数值规范，正负零一致；不做四舍五入，不跨位置或连接合并，不做文本去重。Soniox时间位置同用规范；Flux/Assembly显式turn ID保持原契约。
- 两家目标测试先红后绿，扩展0/0.0、0.0/-0.0及2/2.0：同来源revision=2，ledger只保留12。相关ASR/ledger/控制器/实际SDK编号工具管线 **60 passed / 2.21秒、1依赖弃用警告**。ruff、相关mypy和diff检查通过。[证据](development-20261022-r24/)。本轮未重跑完整后端；最近r23全后端584项加之后独立安全测试通过，不能把60项说成全后端。
- 只读复核官方Jev首页/quickstart/API参考；未使用真实Key、未读账户计费页或调用推理，不采信第三方价格作为费用授权。

仍未完成：混合缺时间快照完整处理、未知范围可靠恢复与重连时钟；真实六模型/厂商；RTC精确任务回执和编号缓存串行组合；精确指标；完整UI状态/视觉/可访问性；真实弱网/手机/实机AEC。不以来源规范证明这些项通过。无新增产品决定，无独立PASS/Gate2/提交/推送/部署/主规格合并/归档。隔离服务8765/5174和/tmp/voiceagent-td-r15测试数据、忽略的NLTK资源保留。
