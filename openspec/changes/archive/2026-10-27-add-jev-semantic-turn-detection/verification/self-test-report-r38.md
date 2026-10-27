# 研发自测报告 — 第三十八轮Jev最小真实联调

**IN PROGRESS / NOT READY FOR INDEPENDENT REVIEW。**

D-053逐批授权后，仅通过正式JevClient发送计划中的两条虚构英文文本，最多2次、上限US$0.01、3秒超时、不重试。两次均ok，实际模型jev-1.14.0；让出轮次概率分别0.85/0.04，完整/未完整概率分别0.8/0.2和0/1。耗时1021.617/265.974ms；输入总计756 token，按公开$0.042/M输入、输出免费的单价估算US$0.000031752，非账单核销结果。未发送录音/客户数据，未调用ASR/TTS。

发现版本差异：官方models页本轮核验仍称jev-latest→1.13.0，实际返回1.14.0。保留响应版本，不静默改正式配置。两例不证明语言效果、P95或完整实时联调。

离线授权缺失、精确范围、CLI先授权后读Key、401不重试、正常请求/白名单结果及第二请求失败不借用旧usage，共7项通过；ruff通过。原始缺模块红测试和后续结果保留development-20261022-r38/；未重跑完整后端，最近完整回归为r37的635项通过。

剩余：完全未知ASR范围/跨连接时钟、RTC逐任务与编号缓存串行组合、精确历史指标、完整UI A/B/视觉/可访问性、真实六ASR/TTS、手机/弱网/实机AEC/容量。当前不交独立审核，不填写PASS/Gate2。详细最新状态见delivery-status.json。

证据：development-20261022-r38/external-results.json、jev-smoke-plan.json。忽略的安全白名单厂商日志在scripts/vendor/typesafe/logs/jev-synthetic-smoke-v1-D-053.log；不含Key。未提交、推送、部署、合并主规格或归档。
