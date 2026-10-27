# 浏览器兼容性与失败清理（2026-10-27）

## 已确认根因
用户明确报告 Task playback is unavailable in this browser。此字符串只由prepareRTCPlayback必需能力门禁抛出，尚未发RTC offer，不涉及ASR/Jev/LLM。生产日志UA是荣耀Android浏览器、Chrome97；不能用UA单独断言全部能力，但错误正文证明至少一个必需接口不存在。
Chrome官方141说明：https://developer.chrome.com/release-notes/141#webrtc，标准新版Encoded Transform在141发布，2020已发布旧版。WebCodecs Chrome94说明：https://groups.google.com/a/chromium.org/g/blink-dev/c/6knQoJRpje4 。当前代码只绑定新版ScriptTransform，旧版createEncodedStreams未实现；荣耀定制内核的WebCodecs/Opus细项未经设备探测，不能承诺简单旧接口替换即可支持。

## 本轮修复
Bearer认证的连接前失败事件可以原子取消其pending lease；不能取消另一个会话或active会话。立即归还名额，清除凭证并将历史标failed/not_started/playback_unsupported。
错误上报3秒截止；上报和媒体清理并行启动，清理不等遥测。SDK stop在没有pc时直接返回导致initDevices设备未释放，因此仅pre-peer路径额外disconnect mediaManager。播放器错误也不跳过后续清理。
错误文本明确说明浏览器不支持编号跟读，不再建议反复重试网络。

## 自测
- pytest全量793 passed、9 skipped（/tmp/voiceagent-preconnect-pytest.txt）；前端node28 passed；ruff/mypy通过。
- 正式本地页面td-rtc-preconnect.spec.js 1 passed：禁用ScriptTransform，真实本地API连续4次分配→失败→取消，每次pending/active为0、错误回执204、历史failed/playback_unsupported、不发offer、不调用厂商。
- 首次错误HTTP响应人为挂起，验证所有真实浏览器假麦克风track先ended，再放行响应；修复前此断言失败，修复后通过。
- 原正式RTC编号跟读td-rtc-identifier-entry.spec.js 1 passed，证据/tmp/voiceagent-preconnect-normal-rtc。
- 测试库/tmp/voiceagent-preconnect-20261027；Playwright产物test-results（忽略）；未发送真实客户数据，无收费调用。一次从仓库根误运行npx未成功安装，随后均使用frontend已有依赖与--no-install，未修改依赖。

## 尚未完成
旧荣耀浏览器仍不支持当前播放器。这不是名额释放修复能解决的问题；必须为旧接口做独立适配和实际RTP/解码/停止证据验证，或使用具备所需能力的浏览器。本轮没有绕过任务身份验证、回退无跟读音轨、改数据通道音频或新增解码依赖。真实手机、AEC、弱网未验。
