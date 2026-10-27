# Independent review — intake backpressure

- Reviewer: /root/intake_review，加载change-verifier，2026-10-27，只读审阅。
- Scope: worker接收解耦及mapping-first测试，不含新恢复政策。
- Patch result: PASS（未发现新增阻塞缺陷）；独立运行10项worker测试通过。
- Overall incident: INSUFFICIENT EVIDENCE，不代表手机故障已解决，不授权整体验收/上线声明。
- 保留有序解码、身份校验、100条队列与原截止；void deliver解除读取背压。
- 额外缺陷RTP-RETRANSMIT-LEDGER已登记：发送包装重传时重复消费编码证据；直接启用NACK不安全。
- facc564a的decoding=false无法排除更早背压，也不能证明背压为此次根因。
- 保持RTP、身份与既有截止的有界原包重传可另做工程验证；重播整段、延长等待或容忍缺包需要明确产品取舍。

## 新增诊断复审
同一独立reviewer限定PASS：相关Node28/28、API11/11、close守卫后entry16/16。安全数值白名单，无原始stats/音频/地址；采样迟到结果不更新，首错同步缓存读取不新增等待。真实手机整体仍INSUFFICIENT EVIDENCE。后续age起点由返回改为请求开始，避免慢采集旧值伪新鲜。

发布前最终复核：reviewer已确认requestedAt计龄及peer创建前closed守卫，限定PASS、可发布本补丁；不代表手机根因、整体修复或Gate通过。
