# 静音缺包与关闭清理修复

生产最新64e3e81e（13:07UTC）packet_deadline，已核对mobile GET200加载demo-BRbfGyA5和worker-XmC5jSd4，服务端2514614；失败前无user_turn_start/interrupt证据，失败后旧clock请求持续约30秒。不得猜旧缓存或把本地同类复现当手机唯一根因。

离线红测：第12包静音缺失、前序90ms每包解码，触发packet_deadline；关闭后start引发新请求。修复后两项转绿，Node41通过。

浏览器初次压力探针丢第25包未触发旧超时（deadline前已到队首），预期旧错误断言失败；属于未成功触发指定时序的探针，未当通过。首次trace保存/tmp/voiceagent-silence-old-138/initial-probe-trace.zip；改第34包制造更深队列，同时要求来源span为null。

Ruff首次发现新增测试局部import缺空行，已修正。

## 最终验证
- 本地全后端810 passed/9 skipped；Node41 passed；Ruff、mypy79源文件、build通过。
- Chrome138旧条件最终重放：/tmp/voiceagent-silence-old34-cleanup-138，packet_deadline，92packets/85mappings/27decoded、目标silence、队首matched、解码运行中。诊断成功HTTP204保存；active0、所有麦克风track ended、1200ms无新clock请求。
- 新条件Chrome138：/tmp/voiceagent-silence-fixed-138，523decoded，1个完整来源静音退休，6个真实播放回执204，无失败；普通回答/跟读/清空/停止均通过。
- 新条件Chromium153桌面+窄屏2 passed：/tmp/voiceagent-silence-fixed-modern，命中注入/静音来源/慢job断言。每项目worker诊断单独保存，回执文件只保留末项目，不声称两份独立回执文件。
- 自动诊断仅有界数值/枚举和client/worker资源文件名；API拒绝未知字段、任意URL/文本、负数/超限/字符串计数，原Bearer及任务证据保护不变。
- 关闭后control不再处理，sampler.close不可重启；不依赖用户查日志。
- 独立审核packet-silence-review.md为局部补丁PASS；生产手机64e3e81e原首错类型已确认，但旧日志缺少目标范围，不能推定就是本地这次静音缺包。
- 专用隔离库/tmp/voiceagent-silence-20261027、日志/tmp/voiceagent-silence-server.log；保留本地、不提交，无收费调用或真实录音外发。
