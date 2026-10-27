# 移动端连接后失败调查

最新会话096cb487-dbb2-454c-b490-89e83d829870，服务端11:08:06–10 UTC。

- ICE completed、session_connected，麦克风音频已进入管线（ASR使用1.279秒音频），不能归因于UDP未通或旧API能力门槛。
- 客户端先上报mobile_call_error/provider/call_interrupted，之后connection_failed，均stage=signaling；服务端随后正常取消管线。
- mobile-demo.js的prepareRTCPlayback onFailure忽略reason，统一为call_interrupted；startCall catch又显示通用connect错误。因此截图不是根因。可能播放器验证或远端audio.play失败，现有记录不足以区分，不能认定Jev或厂商失败。
- 需补安全错误枚举与首错保护、移动正式路径回归，再确认实际具体原因；未发起额外真实厂商调用。
