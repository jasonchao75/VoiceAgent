# RTC 独立代码评审（2026-10-26）

范围：r87 工作区的开发 RTC 候选，RTP 任务身份、解码/播放、认证回执、输入源及渲染时钟。未修改实现；没有外部服务调用、手机/声学或弱网实测。本报告是完整独立评审的分项输入，不自签整个 Checkpoint C。

## 结论：BLOCKED（有一项确认实现缺陷）

### RTC-REVIEW-001：回执请求挂起会阻塞全部后续停止/结束回执

- 位置：`frontend/src/td-rtc-entry.js:49-57`；后端依赖点 `src/pipeline/serial_output.py:351-380`。
- 触发：RTC 本身仍连通，但第一条 `/playback-events` 请求长时间无响应。浏览器已实际播放甚至停止旧任务，后续 `task_stopped`/`task_finished` 被前一条串行 Promise 挡住。
- 原因：回执 `fetch` 没有超时、AbortController 或独立故障截止；`receipts` 串行等待其完成。后端正确地不猜测已停止，但 active 输出槽没有专用回执失联截止，导致 Final 新回答/下一编号任务持续等候。只有整通话 idle/max 截止可兜底（默认 300/1800 秒），不能提供及时可解释的播放失败。
- 影响：用户可能经历长时间无声，新输入仍能进入处理而输出无法推进。此项为可复现的故障处理缺口，不是把尚未测过的弱网音质笼统算作缺陷。
- 修复边界：为回执发送增加有界截止、关闭时取消挂起请求；回执无法确认时显式结束/报错并保留未知事实，不能伪造停止回执或直接允许新答叠播。后端应提供独立的有界停止确认保护，避免完全依赖浏览器异常回调。
- 所需回归：①started HTTP 保持 pending，随后真实 stopped；②服务端已收请求但响应丢失；③关闭通话时 pending；④Final 新答不能越过未确认旧任务，也不能默默等到全局通话超时。应保留合法回执顺序/幂等。

### 离线复现

复现脚本 `rtc-review-receipt-hang.mjs`（本目录） 导入生产 `prepareRTCPlayback`，仅替换浏览器 API 和 fetch（无网络），让第一次回执 fetch 永久 pending；依次注入真实桥接入口需要的 `task_started`、`task_stopped` 消息。检查第二次请求不会启动、失败回调不会触发、请求没有 signal；静态核对该路径没有定时截止。

运行：`node openspec/changes/add-jev-semantic-turn-detection/verification/stage-review/rtc-review-receipt-hang.mjs`

实际结果：`{"requestsStarted":1,"failureCallbacks":0,"stopReceiptBlocked":true}`。等待 100ms 本身不用于证明长时间故障；无任何超时/取消路径由生产源码控制流确认。

## 已复核且未发现新增确认问题的部分

- RTP 音频仍走原轨道，控制通道只传身份/范围/摘要；开发候选与默认原链区分。
- 服务端 source→Opus→实际 RTP payload 摘要，客户端对应 packet decode job 和任务范围；未采用含糊的时间戳近似匹配。
- 客户端 actual render quantum 发出开始/结束/停止事实；不是把服务端入队当开播。
- API 使用当前 session token；源范围只匹配服务端观察到的 PCM、连接代次和同包摘要。
- 时钟范围采用双端因果锚；缺失/过期证据保持缺失，不以 RTT/2 冒充精确时间。

## 独立执行证据

`.venv/bin/python -m pytest -q tests/test_td_rtp_input.py tests/test_td_rtp_mapping.py tests/test_td_rtp_writer.py tests/test_rtp_capture_clock.py tests/test_render_clock.py tests/test_playback_receipts_api.py tests/test_td_serial_output.py`

结果：**27 passed，2 warnings，1.97s**。警告来自已安装依赖弃用。现有测试通过不覆盖上面的挂起回执缺陷。

仍未验证：真实浏览器网络丢包/延迟矩阵、手机/Safari、物理出声/AEC、真实厂商整链取消以及正式默认采用。它们已有研发披露，本报告不作为新增缺陷重复登记。

客户端独立执行 `node --test frontend/tests/unit/*.test.js`：**20 passed，2.08s**。

生产文件未改。复现脚本保留本报告同目录；`/tmp/rtc-review-receipt-hang.mjs` 为同内容初始临时副本，不提交。主评审已统一登记回执挂起问题到 delivery-status.json。
