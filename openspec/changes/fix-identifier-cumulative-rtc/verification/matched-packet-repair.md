# 已匹配包误超时修复（2026-10-27）

## 修复范围

worker旧条件：收到音频包1000ms后，只要packets仍含该包就报mapping_deadline。数据报先到、可靠标记随后到达且前序解码占用时，两份证据已经齐全，包仍在等待解码，被误报为缺标记。

改为只在包仍在且其映射不存在时触发mapping_deadline。已齐备的包继续严格按来源顺序解码；实际缺映射仍1000ms失败，单次解码卡死仍1000ms失败，队列仍限制100条，hash及采样范围校验不变。没有增加超时，没有丢弃任务音频或伪造回执。

## 红绿证据

- 离线worker重放：音频先到，30ms后全部映射到达，每包解码90ms。旧代码6项中该项失败，修复后8项通过；新增真实缺映射与单次解码1200ms仍失败的负向用例。
- Node全套：38 passed。
- local-real Chrome138.0.7204.183，网站登录保护开启、扫码无Cookie、正式页面与RTP、厂商离线替代：标记延迟150ms，前35包每包增加60ms解码等待。新代码完整跟读、停止、清空通过，418包绑定、最大等待1612.3ms、35个真实延迟job、无mapping_failed、6个回执204。保持实际Opus解码器和AudioWorklet。
- 同一浏览器同一场景，仅测试响应重放旧判断，重现mapping_deadline（预期失败断言通过）。没有覆盖或回滚生产源码。
- 测试断言注入替换命中、至少35个慢job及等待超过1000ms，防止未来注入失效却假通过。

## 失败压力探针及边界

最初持续给每包增加35ms的压力探针触发packet_queue_limit（216包到达、208映射、114已解码）。这是持续处理慢于输入时的既有过载边界；不能把本修复描述为支持无限积压。后续短时压力只在首35包施加，验证恢复后不误断线。真实手机持续解码能力尚未验证。

## 证据与隐私

`/tmp/voiceagent-matched-old-chrome138`保存旧条件对照；`/tmp/voiceagent-matched-burst-chrome138`保存新条件真实浏览器回执与worker数据；`/tmp/voiceagent-matched-burst-current`为新版浏览器。持续过载探针在`/tmp/voiceagent-matched-chrome138`。隔离库`/tmp/voiceagent-matched-20261027`，服务日志`/tmp/voiceagent-matched-server.log`，仅保留本地不提交。无收费调用、无真实录音外发。

## 不能宣称的结论

生产c83ac9ba/8373a6e7确实报mapping_deadline，但旧生产遥测无匹配/解码队列快照，不能证明手机两次只由上述条件触发；也不能宣称所有安卓/弱网已通过。此次交付是已独立复现的播放器缺陷修复，用户最终真机验收仍待完成。

## 新版浏览器补充

现代Chromium153窄屏通过；同批桌面一次在会话创建前超时（仅demo读取及view/start事件，没有麦克风完成或会话创建请求，尚未进入worker）。原参数/原代码单独重跑桌面通过，证据`/tmp/voiceagent-matched-burst-current-desktop-repeat`。该首次模拟麦克风挂起原因未唯一确定，保留失败记录，不删除、不算通过。构建通过。

首次失败trace被Playwright重跑清理，当前仅保留首次worker诊断；network结论来自开发者当时读取，独立审核不能重查该trace。此证据缺口已登记。
