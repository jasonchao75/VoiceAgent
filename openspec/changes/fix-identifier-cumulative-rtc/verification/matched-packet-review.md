# 已匹配音频包误超时：独立审核

- 日期：2026-10-27。
- 审核者：`matched_packet_review`，未参与实现，未修改产品要求或验收状态。
- 结论：**PASS（限定已匹配包等待有序解码时被误报 mapping_deadline 的工程修复）**。
- 此结论不代表生产手机两次失败已唯一定位，也不代表真实安卓/弱网体验验收通过；线上发布仍需CI/CD及健康复核。

## 对照契约与实现

读取了本Change proposal、design、Delta spec、tasks、decisions和生产两次核查记录，并对照主规格的客户端真实开播、停止确认和证据约束。无页面布局或冻结原型变更。

旧逻辑只要RTP包仍在packets中就判缺少mapping。在“RTP先到、控制映射随后完整到达、前序解码尚在运行”组合中，包尚未消费并不表示映射缺失。新条件同时要求packets存在且mappings不存在，修复这个错误状态判断。

核对完整消费链：decodePacket同步取出并删除同一ID的包和映射，再校验payload SHA-256、来源连续性、解码extent；已匹配排队不产生PCM或伪造回执。真实缺映射仍1000ms失败；单个解码job仍1000ms失败；映射/音频队列各100条限制保持；缺任务音频仍失败。未放松身份、样本范围或停止契约，未增加传输协议和超时数值。

## 独立执行与证据核对

- 独立执行`node --test frontend/tests/unit/td-rtp-decode-job.test.js`：8 passed。覆盖已匹配慢解码恢复、真正缺映射、单个解码卡死、缺任务音频拒绝、来源静音缺失、RTP乱序及extent不一致。
- 独立执行`node --test frontend/tests/unit/*.test.js`：38 passed、0 skipped。
- `git diff --check`通过。
- `verify_change.py fix-identifier-cumulative-rtc`：0 errors；仍有已登记生产首因/真机/持续解码能力及未完成交付任务警告，不据此声称整个Change验收完成。
- 开发者运行的本地真实Chrome138产物，经本审核者直接读取核对：`/tmp/voiceagent-matched-burst-chrome138`。engine=138.0.7204.183；418包绑定、35个job解码耗时>55ms、最高匹配等待1612.3ms，无mapping_failed。6个播放回执均204，包含真实task_started、task_finished及task_stopped（273408样本）。无播放HTTP错误。注入延迟确实执行，未绕过真实codec、RTP身份或AudioWorklet。
- 同一真实Chrome138、同一短时慢解码和映射延迟，恢复旧判断的负向产物`/tmp/voiceagent-matched-old-chrome138`：mapping_deadline、packets=72/mappings=64/decoded=20；正式页面上报204且保留同一安全失败原因。红绿对比支持本次修复的局部因果关系，不等于复现用户手机全部环境。

## 发现与边界

未发现阻塞本次局部补丁的新增缺陷。审核建议补充的浏览器注入替换命中、至少35个慢job及最大匹配等待超过1000ms断言已加入，静态复核确认，避免测试源码变化后注入失效造成假通过。

持续人为增加每包35ms的压力探针最终packet_queue_limit终止，表明持续解码能力低于音频实时速率仍不能工作；不能以本次修复承诺此类设备兼容。此项已登记SUSTAINED-DECODE-CAPACITY。未运行收费厂商API、未进行真实安卓硬件/弱网/AEC测试。

## 补充：现代浏览器复验与首次启动失败

本审核者直接读取以下保留产物：

- `/tmp/voiceagent-matched-burst-current/rtc-probe-diagnostics.narrow-chromium.json`：Chromium153.0.8010.12，421个绑定包，最大等待1609ms，35个慢job，无worker失败；对应6个播放回执均204。
- `/tmp/voiceagent-matched-burst-current-desktop-repeat/rtc-probe-diagnostics.desktop-chromium.json`：同版本desktop原条件独立重跑，426个绑定包，最大等待1603.8ms，35个慢job，无worker失败；对应6个播放回执均204。
- 首次desktop的保留diagnostics为同版本，workerEvents为空。开发者此前读取的trace显示仅demo GET200和两个events204，没有mic_permission/session请求，停在connecting；**该trace已被Playwright重跑清理，本审核者无法独立复核其网络记录**，该部分只能注明开发者先前读取，不能写成独立确认。

首次失败已登记为`MATCHED-MODERN-TEST-START`，精确启动原因仍未知，不能因重跑通过就标为已修复。保留诊断没有进入本次worker路径的证据，且不修改实现/阈值的同条件重跑已真实完成，因此**不阻塞本次已匹配包计时条件的局部补丁PASS**；但它仍限制对整体扫码连接稳定性、测试可复现性或手机问题彻底解决的声明。原trace留存缺口同样必须披露并保留在交付记录中。
