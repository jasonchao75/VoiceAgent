# D-071安装顺序修复：短开场实际闭环已证明

1连接、源含静音≤2秒，无Final/编号/厂商请求；本批已停止。实际task_started128样本、task_finished5760样本均鉴权204，无mapping_failed，编码帧/解码已进入正式入口。

原浏览器脚本因硬编码4800结束样本而失败，保留browser-original-failed.txt，未重跑。对失败trace离线取出真实task_end expected_samples5760，与实际结束5760精确一致，recorded-manifest-audit.json含核验。锁定SDK默认40ms(960个24k样本)分块，2400样本补齐2880，转换48k后5760，解释差异。不是按观察值篡改契约。

提前安装与移除测试原生分析器联合修复获得此证据，未分别隔离两者贡献，不声称哪个是唯一根因。这个短开场仅关闭入口接包/短任务渲染问题，不代表正式Final/编号、完整历史或延迟通过。

D-071批次到此结束。后续按仍有效的D-068开发环境正式集成任务验证Final/编号及同输入延迟，保持默认旧链、不收费、不部署；不把D-071扩充为其他场景的批次授权。测试临时数据/tmp/voiceagent-d071-formal，原始日志/tmp/voiceagent-d071-server.log忽略且不提交（含临时能力URL/本机地址）。
