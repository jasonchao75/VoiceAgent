# 静音缺包、关闭清理与安全诊断：独立审核

- 日期：2026-10-27。
- 审核者：`matched_packet_review`，只审阅实现、执行验证和写本报告，未实现修复。
- 结论：**PASS（限定本次已复现工程缺陷与安全诊断接线）**。
- 不代表生产手机64e3e81e首因已唯一证明；该会话仅留下packet_deadline，不能追溯其目标包是否为静音。真实手机与弱网整体验收仍未通过。

## 契约与实现核对

已读取当前Delta、design、相关任务及主规格播放证据契约；本次不改页面布局、用户配置或冻结原型。

1. 非队首缺包若其服务端来源span完整为null，旧定时器会误判任务音频缺失。修复仅将其标记expiredSilence；只有有序drain到达该范围时才退休。不会在前序解码期间跨序修改nextSource，不产生虚构PCM或播放成功事实。
2. expiredSilence随解码或退休清除，受mappings既有100项上限约束。任务音频缺失仍packet_deadline；真正缺映射、单job卡死、hash/extent/来源不一致仍失败。未增加超时数值或取消队列保护。
3. RenderClockSampler.close变成不可逆终态；迟到start/pulse不能恢复请求。RTC close先设置closed，control入口拒绝迟到mapping/input epoch，后续关闭调用幂等。原有fetch abort、pending拒绝、worker终止和AudioContext释放保留。
4. 首错诊断只携带包计数、有限队列长度、布尔状态、枚举和安全构建文件名；不携带RTP payload、转写、音频、地址或token。API nested model extra=forbid，整数strict且有界，构建名只接受最长100的文件名字符；非mobile_call_error不能附诊断。
5. events端点原有pending/active session Bearer鉴权及会话归属不变；diagnostics持久化和日志发生在相应凭证验证之后。首错保护仍由failCall/bridge的既有一次性状态保证，不用清理时401覆盖首错。

## 独立执行

- `node --test frontend/tests/unit/*.test.js`：**41 passed**。包括新增非队首静音缺包慢解码恢复、关闭后迟到控制不重启clock，以及原有任务缺包/卡死/extent失败保护。
- `/tmp/voiceagent-r91-py311/bin/python -m pytest tests/test_publication.py tests/test_playback_receipts_api.py tests/test_auth.py -q`：**34 passed**。验证错误token拒绝、通过鉴权的诊断保存、任意字段/负数/越界/字符串计数/URL构建标识拒绝。
- 门禁0 errors；仍有已登记手机根因、历史测试/真机范围及本轮部署任务警告。本报告不代替这些问题关闭或产品接受。

## 开发者浏览器产物的独立核对

本审核者读取产物，不冒认自己重新执行浏览器：

- `/tmp/voiceagent-silence-old34-138`：真实Chrome138.0.7204.183，旧定时条件重放，packet_deadline；诊断显示head_state=matched、target_kind=silence、target_has_packet=false、target_has_mapping=true、decoding=true，pending_packets=63/pending_mappings=57。正式mobile_call_error为204，并携带client_build/worker_build，证明诊断完整接通。
- `/tmp/voiceagent-silence-fixed-138`：同类型真实Chrome138压力组合修复后523包绑定、0 mapping_failed；按序跳过source_start=32328/samples=960的已证明静音，最大匹配等待1579.3ms；6个真实播放回执均204，包括task_finished及task_stopped（276520样本），无播放HTTP错误。
- 首次第25包探针未触发旧条件的预期失败，不算红测成功；开发者保留`/tmp/voiceagent-silence-old-138/initial-probe-trace.zip`并记录随后第34包深队列才复现。不存在把首个未复现结果隐藏成通过的证据声明。

## 剩余边界

无新增阻塞本次局部补丁的缺陷。生产64e3e81e是否正是上述静音缺包分支仍未知，新诊断只对之后的失败有效。真实安卓设备持续解码能力、丢包/弱网、AEC、收费厂商端到端未在本审核中测试。部署及真实生产健康需主Agent后续核对；不得用本报告声称手机问题彻底解决或User Gate2通过。
