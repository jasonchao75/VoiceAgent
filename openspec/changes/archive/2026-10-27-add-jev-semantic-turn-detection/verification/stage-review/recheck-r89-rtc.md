# r89 RTC独立复审（2026-10-26）

## 分项结论

**本次RTC返修复核通过，未发现新增确认代码缺陷。** 此结论限已审的软件修复与已有本机证据，不单独签全Change PASS、完整Checkpoint C或用户Gate2。未修改生产实现，未调用外部厂商，未重复付费/有限实验。

## 原问题关闭依据

1. **回执HTTP挂起：已修复。** `frontend/src/td-playback-receipts.js`以串行发送保持顺序，但每条有3秒Promise.race截止、AbortController；close中取消并settle pending请求；失败只回调一次，后续任务不能绕过不确定的停止事实。`td-rtc-entry.js`通过bridge.fail发真实播放器interrupt，再进入正式页面failCall；页面错误遥测不再阻塞media释放。服务端`SerialAudioOutput._guard_stop_confirmation`另有5秒守卫，以永久错误结束、不伪报stopped或放行新音频。原缺陷不再存在。
2. **SDK晚赋/替换track来源漏观察：已修复。** `src/pipeline/rtp_input.py:observe_native_reader`在实际原生Resampler.resample入口观察decoded帧，再调用原resampler并返回原outputs。未固定早期track，仍由锁定SDK读取；PCM、时间戳、格式不改。finally只恢复仍归本observer持有的resampler。SSRC、同包hash、PCM一致性、连续覆盖等条件没有放宽。
3. **证据等级保持正确。** r89冷/暖两通严格RTC_E2E结果为local-real媒体/HTTP/Worklet/SQLite，但推理仍是替身；设备/厂商完整效果未被冒称通过。初始诊断slots错误和r88缺快照的历史归因边界保留。宽E2E区间不代表精确延迟或低延迟达标。

## 本次独立运行

```sh
.venv/bin/python -m pytest -q tests/test_td_rtp_input.py tests/test_rtp_capture_clock.py tests/test_td_rtp_integration.py tests/test_td_rtp_writer.py tests/test_td_webrtc_cancel.py tests/test_td_serial_output.py tests/test_playback_receipts_api.py
node --test frontend/tests/unit/td-playback-receipts.test.js frontend/tests/unit/td-rtc-entry.test.js
```

实际：**30后端passed /2依赖警告/2.07秒；9客户端passed /0fail**。包括原生Opus/PyAV/SDK字节一致性、晚赋/替换track、缺包/SSRC拒绝、停止保护、HTTP已被接受但响应丢失、关闭时取消和正式RTC入口失败联动。

阅读：change-verifier规范、r89 README/repair-review-r89、r88实际回执故障报告及现有生产代码/测试。此次未重跑浏览器冷/暖RTC或全视觉矩阵，沿用已有明确标注的local-real证据；不能把本次离线绿灯当新增浏览器实测。整Change门禁由主评审统一执行。

## 剩余边界

未新发现需登记的实现缺陷。原有手机/Safari/弱网、AEC/硬件声学、真实厂商完整取消、跨连接可靠钟、精确增量延迟/目标容量仍未验证；RTC正式默认采用仍未批准。这些不是本轮新增bug，也不以“还没有最终审核PASS”循环要求研发再造任务。主评审应依范围和现有未验证项判断能否提交用户验收；本分项不代替用户Gate2。

本轮完成RTC返修核查及离线复测；未发现新增问题；上述范围未验证；无需新增产品决定。
