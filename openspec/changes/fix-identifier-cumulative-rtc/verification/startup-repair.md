# 连接后播放失败修复与验证（2026-10-27）

## 结论及证据边界
原生产096cb487通话ICE已成功，随后signaling阶段客户端先报provider错误，再被通用连接错误覆盖。旧实现丢弃具体reason，不能追溯证明该通话唯一根因；不得把本地重现写成真机根因确认。

已在真实桌面Chrome138.0.7204.183中重现两类确定代码缺陷并修复：
1. SCTP控制握手延迟1.4秒：旧发送时序先发51个RTP包而0条归属映射，mapping_deadline断线。证据/tmp/voiceagent-connect-sctp-before。现在等控制就绪再发，首帧重锚发送时钟；10秒仍未就绪则有界关闭。
2. 已证明无任务静音缺包：旧worker离线重放失败，新worker按可靠映射顺序处理，跳过无任务静音且不产生PCM/成功回执；真正任务音频缺失仍失败。初次/tmp/voiceagent-connect-startup-loss包含开场任务，不作为纯静音证据。

同时修复首错覆盖/重复清理、provider分类漏释放pending、offer已claim未连通的active泄漏、取消后迟到注册启动孤立管线，以及未建立capture时历史不结束。

## 验证
- 真实Chrome138，SCTP1.4秒延迟+首3个纯静音RTP包丢失：完整跟读/停止/清空1 passed。/tmp/voiceagent-connect-combined-final，engineVersion实录138（UA可能受Playwright设备模拟覆盖）。
- 纯静音case /tmp/voiceagent-connect-silence-fixed明确null spans、3个silent_packet_skipped，无伪造任务播放。
- signaling阶段decoder_unavailable注入：单次204、安全首因、名额0，history failed。/tmp/voiceagent-connect-signaling-final。
- live阶段packet_deadline注入：首因不被SDK错误覆盖、释放名额。/tmp/voiceagent-connect-first-error。
- SCTP12秒故障注入：服务端沿用10秒边界断开，真实浏览器最终error active、名额0。/tmp/voiceagent-connect-control-timeout-final。合成的阻塞SCTP发送使完整清理用时约26秒，不等同真实网络延迟目标。
- 后端全量800 passed、9既有skipped（/tmp/voiceagent-startup-final-pytest.txt）；最新历史收尾改动后23项定向测试通过。
- Node全量35 passed（/tmp/voiceagent-startup-node.txt），Ruff格式/检查、Python3.11 Mypy 79源文件及生产前端build通过。
- 独立审核见startup-rtc-review.md；新浏览器桌面/窄屏正式路径共4项通过（/tmp/voiceagent-connect-modern-final）。

## 测试中间失败说明
- 首次组合测试连接/跟读未断，但慢握手期间fixture语音提前打断开场，预期2个finished仅有1个；同步延后ASR及VAD脚本3秒后相同功能断言通过，未修改生产交互规则。
- 超时测试初次用toBeVisible误读opacity=0的隐藏error屏，已改为检查active类；复验通过。
- 独立审核发现的pending/provider、无限等待、active取消、capture前历史终态缺口均纳入修复/测试。
- 一次误用Python3.13环境类型检查报NumPy stub版本冲突；改用项目Python3.11且不传额外ignore标志后检查通过，未改业务源码压制错误。

## 未验证及产物
未使用真实客户录音或调用收费厂商。实体安卓/荣耀97、Safari、扬声器AEC、实际弱网和厂商端到端仍未验证；用户此次历史首因不可追溯。
隔离库/tmp/voiceagent-connect-repro-20261027；日志/tmp/voiceagent-connect-*-server.log、浏览器证据上述/tmp目录和被忽略test-results；不提交录音、日志、数据库。只提交源代码、测试与文字记录。

控制超时补充：服务端关闭后SDK可能尝试重连；旧任务worker以multiple_receiver_transform明确拒绝，撤销凭证后的上报为401。该路径证明有限失败与名额释放，不宣称恢复通话成功。
