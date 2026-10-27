# D-073 独立阶段定向审查

2026-10-25；非最终独立验收，不填写独立 PASS、Checkpoint C 或 User Gate 2。未运行 RTC、厂商调用或完整回归。当前代码为工作区增量，审查对象不等于 r74/r75 旧快照。

## 结论与修复项

因果区间实现符合保守夹逼思路，没有使用 RTT/2 或按采样率外推服务器时刻；本次未发现区间数学的可复现失真。发现一个 P2 实时指标展示口径遗漏，应先修复后再宣称 D-073 展示完整。

**R78-STAGE-LIVE-RANGE-ORIGIN / P2**：`frontend/src/main.js` 的 `formatPlaybackMetric`（当前2263附近）显示区间与 response_id，`addLiveMetricCard` 仍称 playback，没有说明 `server_audio_task_prepared` 起点。与此同时 `td-history.js` 明确展示 “Server audio task ready → client render”。旧 `playback_ms` 从 tts_audio_ms 起算，新范围从任务准备起算；实时卡未标区别会让同名指标产生口径误解。修复条件：实时区间同步明示真实起点及区间含义，并定向验证无证据/旧标量/新范围状态；无需新产品决定，也不需要改音频架构。

## 因果与身份核查

- `RenderClockLedger.issue` 在捕获所有者的单调时钟记录 S0；经认证 session 返回随机一次性 challenge；Worklet 只在实际 process 内采样 F；服务器 ack 收到时记录 S1。单个锚证明 S0 ≤ 渲染该帧的实际处理时刻 ≤ S1（以可信客户端代码为边界，认证不能证明客户端未篡改）。
- 目标帧严格大于前锚、小于后锚，同 clock_id / sample_rate；取最强下界 max(S0_before)、最强上界 min(S1_after)。故最终区间保守，网络非对称只增加宽度。等帧不推导，缺任一锚不产生范围。
- nonce 不可改帧/改时钟重放刷新；超过2秒的待采样与锚不用于新界；pending≤8、锚≤32、待任务≤64。空闲锚不持久化，不挤占10,000事件；实际范围保存两条所用锚。
- capture 先按 prepared playback_id 找任务，再按 task_started 的原时钟帧取界；区间减去同服务器单调时钟的 prepared_ms，下界与已知非负因果条件相交。response_id/playback_id/turn_id 一起保存；只向原 turn 的 first_response_id 匹配状态写摘要，Final 后续版本有自己的事件，不覆盖原响应事实。
- 原收件时刻不会写入旧标量播放值；缺 source_end_clock 时不派生 E2E，明确 `source_end_clock_unavailable`。当前获得的仅是“服务器任务准备到客户端渲染”范围，不能声称已实现用户停说到播放的 E2E。

## 离线实跑与证据

独立运行 `test_render_clock.py` 三例，以及 `test_td_history.py` 的关联原响应/不造E2E、存储重启兼容、空闲采样三例：**6 passed / 0.75s**。日志 `d073-review-evidence/targeted.txt`。覆盖非对称时间、跨clock/rate拒绝、过期/重放/预算、原轮关联、SQLite新范围与旧记录保持空值。

审阅 r78 `rtc-fixed/formal-final-history.json` 及 `rtc-range-proof-audit.json`：两响应范围分别约0–32.98ms、19.04–68.79ms，各保留两锚且报告严格同钟夹逼；仅审核既有轨迹，不重跑已消费实验。该证据是 loopback + Chromium + 合成音及离线推断替身，非手机/真实厂商/硬件校准。

## 未审查及后续

未重新执行API鉴权矩阵、浏览器实时卡、完整UI中英/双视口、资源压力、真实厂商或设备。客户端退出/超时与旧NULL迁移作静态审阅并复用已列单例，不能替代完整候选回归。D-073已允许范围，不需要重复询问“接受误差”规则；E2E源端点时钟及实际厂商/手机仍按原任务和授权边界推进。

## P2 修复只读复核

后续核查共享 `formatPlaybackMetric`：现明确附加 `server audio task ready → client render; response ...`，实时卡与历史摘要均调用此函数。核查 `origin-red.txt` 的实际失败原文，确为旧摘要缺起点；`td-timing-history.spec.js` 新390px断言定位 `.history-metric`，修复后 `origin-green.txt` 为1 passed / 871ms。原响应卡另有既有中英说明，此次不改页面结构。**R78-STAGE-LIVE-RANGE-ORIGIN 的代码遗漏已修复并复核，阶段该项关闭**；本轮未自行重跑浏览器或扩大为全部实时通话验收。

额外只读确认 RenderClockSampler 的默认 fetch/schedule/cancel 使用 globalThis 箭头封装，避免将浏览器原生函数作为类成员调用丢失 Window 接收者；`native-globals-green.txt` 1 passed / 505ms，测试要求实际两次请求与零采样错误。测试使用替身端口，不替代 Worklet/RTC组合；既有真正RTC/WS证据仍按各原报告边界引用。未新增产品决定或最终独立通过结论。
