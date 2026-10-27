# 2026-10-27 接收阻塞与真实缺包

## 生产证据（external-real，只读）
- 服务器685e33a，手机facc564a-0647-470d-9274-eb2c8b528184，13:32:59 UTC，Android10 Chrome138。
- demo-zJdFaotf.js / worker-CMWK8wxh.js，确认并非旧版本。
- packet_deadline，110 packets / 97 mappings / 54 decoded；pending56/41，matched35，decoding=false，head_state=missing_task，target_kind=task，target_has_packet=false，target_has_mapping=true。
- 证据只证明截止时任务包未进入应用队列，不区分网络损失与之前背压导致的原生队列丢弃；不能把decoding=false解释为排除此前背压。

## 已修工程缺陷
- transform回调await deliver，读取后续RTP受前序WebCodecs解码阻塞。
- 改为不等待有序drain，尽快让原生流继续读取；保留100条队列、1000ms截止、来源顺序、SHA256及实际播放回执。
- 新mapping-first +90ms/包离线测试：旧代码packet_deadline失败，新代码14包成功。
- worker10项通过，前端Node全量42项通过，构建通过。
- Chrome138正式匿名扫码路径、本机真实RTP/Opus/WebCodecs/AudioWorklet、离线厂商：慢解码35包60ms、控制150ms延迟组合通过（18.7s）。证据/tmp/voiceagent-intake-138。
- 现代Chromium正式同路径桌面15.0s、窄屏14.3s均通过；证据/tmp/voiceagent-intake-modern。
- 此本机证据不是Android硬件或真实手机丢包恢复的证明。

## 恢复能力边界
- aiortc Opus默认rtcpFeedback=[]，现有发送包装不区分初发与重传，同一个合法包第二次绑定会缺编码证据。
- 独立审核确认不能直接开启NACK；需要协商、原包缓存去重、晚包可达性及丢包实验。
- 本机Chrome138只生成recvonly音频offer（无远端连接）：opus/48000/2仅transport-cc，无nack。
- 不自动注入未协商的NACK，不把缺包静默当成功。Q-005是未经确认的恢复提议，已撤回为当前工程阻塞；用户问“为什么会缺失回答音频？”，没有选择重播/漏音，当前不改失败契约。

## 交付状态
局部补丁审核无新增阻塞缺陷；整体手机故障证据不足，尚未部署本补丁。生产仍685e33a。
本地临时证据：/tmp/voiceagent-intake-unit.log、/tmp/voiceagent-intake-138、/tmp/voiceagent-intake-modern、/tmp/voiceagent-intake-server.log；隔离测试数据库/tmp/voiceagent-intake-20261027，不提交。

## 后续受控取证（同日）
- Mock有界live producer每20ms提供1包，容量2；解码每包90ms。旧await读取触发producer丢弃，最终packet_deadline/head_state=missing_task/decoding=false；解耦后14包均处理且零丢弃。
- 这是明确的机制可行性对照，不是Android真实内部队列模拟标准，不能证明facc564a唯一根因。
- 安全首错诊断增加原生getStats累计received/lost/discarded（缺字段保留未知），500ms缓存仅在失败时上报；age从请求开始计，包含采集延迟；在途请求最多1个，关闭不等待也不接受迟到结果。
- 增加worker已完成解码的max_decode_ms和max_intake_gap_ms；不能由max_decode_ms=0推断从未卡住。
- 不记录raw stats/SSRC/地址/音频，不产生外部API测试费用。采样累计值与worker位置不同，原生lost可能含晚到和统计周期差异，不能当具体任务包丢失证明。
- 全量Node47项、publication后端26项通过（4个既有依赖弃用提示），Chrome138成功组合14.7s；注入既知失败8.7s且保存native_received=91/native_lost=0/native_discarded=0、资源名额清理通过。修复不延长播放截止、不重播、不允许漏音。
- 独立审核新采样器发现close后迟到createPeerConnection可能泄漏，已加创建前closed守卫及回归，复核PASS。
- 证据/tmp/voiceagent-intake-diagnostics-138、/tmp/voiceagent-intake-diagnostics-failure-138、/tmp/voiceagent-intake-diagnostics-final-unit.log；临时数据库/tmp/voiceagent-intake-diagnostics-20261027、日志/tmp/voiceagent-intake-diagnostics-server.log均不提交。

## 下一次单次真机复测的证据边界
已准备首错+构建+原生累计接收/丢包/丢弃及年龄+应用队列+解码耗时。若局部补丁上线后仍失败，读取同一通话诊断，不要求用户手动抓包。若原生报告lost>0，只能证明该周期存在丢包；若原生received增长而应用缺包，仅能缩小至接收/匹配链路；没有逐包浏览器内部记录仍不能唯一归因。不得无限追加本机探针或把此轮证明当真机验收。
发布前生产仍685e33a；依据D-001/D-004及用户“那你修好啊，之后自测好、发布上线”的既有授权发布本轮限定审核补丁，不等待产品选择才能继续工程工作，整体问题仍开放。部署结果另记deployment.md。
