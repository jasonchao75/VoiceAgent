# D-068正式入口实际接入：未通过，已停止

## 已接
正式demo路由/DOM、真实public session/offer/PATCH、原生RTP任务映射适配、现有SerialAudioOutput、Worklet与鉴权playback-events及历史。create_app显式参数仅测试构造启用；默认false，无页面控件或默认替换，无收费调用。

## 实际结果
首次真实本机页面通话失败：Worklet内部started字段未筛选，严格API 422。已改为白名单字段，离线serializer回归通过。定向复测仍失败：2条task_stopped回执204，但rendered_samples均0，不能充当开播或可听取消证据；服务端writer出现10秒超时。通话失败自动结束。测试错误地等待通话结束才持久化的history事件，并在错误页尝试点击end，最终45秒超时；这一脚本等待错误与writer超时分开列，不能改断言冒充闭环成功。脱敏回执见authenticated-receipts.json。

## 结论与停止边界
鉴权/严格回执接收已取得局部证据；正式任务映射/实际开播尚未证明。无法由现有日志唯一确定sender退出、输出队列或客户端映射的根因，不能认定技术不可行。按D-068停止进一步组合/延迟测试；不重启泛用调查，不换架构、不扩大时间容差。后续最小定位应围绕现有sender退出异常/编码与控制记录计数进行一次有界观测，先补缺失证据，再决定能否修复并验证正式闭环。

## 未验证
Final实际开播/停止、正式编号组合、同输入延迟对照、移动/弱网/物理播放与最终完整回归。r59隔离通过不替代正式通过。

## 证据及环境
定向后端7passed，JS字段检查1passed；ruff通过。Python3.13/Pipecat1.8.1、项目锁定前端依赖和Chromium。失败trace/screenshot在test-results/playwright/td-rtc-entry-formal-mobile-6f5b3-s-through-authenticated-API-desktop-chromium/（忽略产物，含临时本机会话能力令牌，不提交）；临时DB/录音/storage.key在/tmp/voiceagent-d068-formal（不提交、不打印密钥）。本轮服务端8793及Vite5178均已停止。未自填独立PASS/C/Gate2。
