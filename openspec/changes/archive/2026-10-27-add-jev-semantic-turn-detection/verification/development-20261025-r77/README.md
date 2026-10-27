# D-073 时钟关联后端底座

## 实际改动

新增RenderClockLedger与认证live-session playback-clock challenge/ack接口。服务器发出挑战后，AudioWorklet观察坐标并回报的真实时刻只能处于发出/收到之间；严格位于两个实际frame锚之间的播放事件，得到同一服务端monotonic时钟的保守上下界。只用先后关系，不把样本差换算成服务器时间，不取RTT/2，不把收件时刻当实际开播。

每会话最多8个pending、32个锚；2秒后失效而不是外推。nonce只归属一个clock/rate、重放不刷新边界、冲突时间序列拒绝。2秒/8/32是可回退工程资源保护，不能算用户可配置产品默认或延迟SLA。

## 证据

- clock-red.txt：初始模块不存在的收集错误，仅证明底座缺失，不冒充行为断言红灯。
- clock-api-red.txt：正式API返回405，目标认证接口尚不存在，实际目标用例失败。
- clock-green.txt：3项纯时钟不变量通过。
- backend-targeted.txt：时钟/API/旧回执/TD历史/原历史30 passed、2依赖警告、1.54秒。
- Ruff相关文件通过；render_clock/capture两模块Python3.13 mypy通过；不是全仓类型检查通过。

## 仍未接通

客户端Worklet挑战采样、范围派生到不可变任务/响应及原轮次、API/SQLite重启、正式历史范围展示与浏览器组合尚未实现。该底座不让旧空值自动变数值，不回填历史，也不默认采用RTC候选。没有新增收费调用或真实设备验证。完整D-073和总体交付仍未完成。

## 依据

Web Audio官方草案说明currentFrame属于正在处理的音频块；getOutputTimestamp给出performance时间估计，准确性依赖与输出位置接近程度，currentTime差不能直接作为可靠输出延迟。故这里不依赖该估计建立虚假的精确误差保证：只记录受认证协议的因果包围。工作let渲染不是硬件声学出声证据。

来源：https://webaudio.github.io/web-audio-api/#dom-audioworkletglobalscope-currentframe 与 https://webaudio.github.io/web-audio-api/#dom-audiocontext-getoutputtimestamp （2026-10-25查阅；草案，不据此声称移动兼容通过）。
