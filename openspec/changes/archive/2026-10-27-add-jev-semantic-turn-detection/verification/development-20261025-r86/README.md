# r86：RTC上行来源前置闭环（2026-10-25）

## 结论

保留RTP、原麦克风/codec/decoder/resampler与PCM，开发候选已证明：**浏览器原生captureTime → 同SSRC/RTP timestamp/payload hash → 服务器decoder PTS → 实际16k PCM区间**。正式RTC取得4个同包、7段重采样区间对应；原有Final实际停播/重答通过。尚未接认证采集时钟锚/候选冻结/持久化RTC E2E，**不能宣称RTC端到端指标已完成**，也未正式采用候选。

## 本轮改动与正式路径

- `src/pipeline/rtp_input.py`旁路记录锁定aiortc的实际时间映射/解码入队边界，以不可变连接ID/SSRC/原RTP timestamp/payload SHA绑定编码源。记录实际AV decoder与resampler时间基，不用SDK原raw.pts猜processed位置。
- 原生SDK第二块PCM确实包含上一包尾部：第一块304样本，第二块320样本，第二块48k媒体区间[912,1872)，跨原包[0,960)尾部与下一包。原始字节/采样率/声道/raw.pts均保持，缺帧/缺包/时间缺口不插值。有界256编码/256解码记录，64个待processed记录。
- 仅`create_small_webrtc_transport(candidate_playback=True, custom_td=True)`安装。默认False及原生/off不新增输入钩子。None/非AudioFrame保留原SDK容错；SSRC从首次接收必须稳定，变化就停止证明、清记录，音频仍走原路径。不冒充跨SSRC/重连支持。
- `td-rtp-input-tap.js/worker.js`在开发候选sender原样放行同一编码frame，异步hash，不等待hash再发音频；最多8个未ack元数据。缺captureTime不以performance.now替代。optional sender能力失败不破坏原接收/播放，关闭销毁worker。默认RTC不安装，不传数据通道音频。
- 根公开demo正式组件/认证回执/历史路径不变。fixture的`/api/_test/td-rtp-input`仅本机测试进程、显式环境开关下提供8条上限诊断，正式应用没有此端点。没有配置页研发控件或另造验收页面。

## 实际验证与证据级别

| 检查 | 实际结果 | 证明边界 |
|---|---|---|
| 既有SDK原行为红灯 | native-behavior-red.txt，缺processed/RTP证据断言失败 | 真正行为红灯；ingress-red.txt最初模块缺失不当作行为红灯 |
| 原生Opus/PyAV/锁定reader、缺口、None、有界、SSRC、开发入口及既有RTC取消 | ingress-final.txt：16 passed /0.78秒 | local SDK/fixture，无远程厂商 |
| 最初开发入口未安装旁路 | entry-red.txt明确调用次数0→安装通过 | 开发选择器行为，不改变默认链 |
| 实际正式RTC上行/Final停播重答 | native-formal-browser.txt：1 passed /7.9秒 | local-real RTC/Worklet/HTTP/SQLite，ASR/LLM/TTS/Jev替身 |
| 新sender captureTime同包对应＋原Final组合 | capture-formal-browser.txt：1 passed /8.0秒 | local-real浏览器/真实RTP与native codec/resampler；非物理ADC/声学 |
| 完整已有客户端单元 | client-final.txt：18 pass /0 fail | mock；不是浏览器兼容 |
| 类型/质量/构建 | lint-final.txt全4相关源通过；mypy-final.txt两源通过；capture-build-current.txt Vite通过 | static/build，不当运行事实 |

正式捕获文件在server-entry/、capture-entry/：第一阶段证明服务器链，第二阶段joined-browser-native-source.json证明4个不同RTP包及7个PCM部分匹配；不能把7个匹配部分说成7个不同包。浏览器10条元数据captureTime从181ms到361ms按20ms递增，所保存匹配包报告201/221/241/261ms。均为该worker性能时钟域的**原生报告值**，不是服务器接收时刻、物理麦克风校准或可直接相减的延迟。

[W3C Encoded Transform](https://www.w3.org/TR/webrtc-encoded-transform/#rtcencodedframemetadata)定义captureTime相对该上下文Performance.timeOrigin；RTP timestamp表示首采样点。当前只做同包和processed媒体坐标对应，尚无跨服务器时钟因果锚，未外推/取RTT一半。没有拿下行映射倒推上行。

实际浏览器结果早于最后SSRC稳定保护拒绝分支；已保存同SSRC真实路径，该补丁只拒绝跨SSRC不再证明，不改同SSRC PCM/坐标。最终16项含SSRC变化/时间缺口拒绝；没有为文档重复已过的真实组合，也不据旧记录声称真实重连已测。

## 失败、修复与未验证分开

- 最初测试诊断端点未走Vite既有/api代理，在开通话前返回HTML，未建立RTC；路径修正后才进行第一正式组合。browser-before-proxy-fix.txt保留，不能称“RTP失败后自动重试”。
- 旁路初版None容错缺失已定向红绿修复；初次import排序/行长已修。SSRC边界代码审查发现的歧义已改为失效保持缺失，不能声称它解决跨连接映射。
- 新sender观察缺少能力时只报元数据缺失，不新增“用当前观察时间”的降级；optional-timing-red.txt和Node检查覆盖不会关闭已有RTP播放。
- 当前未实现：认证同worker采集锚、允许不确定端点的严格输入样本回填、VAD候选边界冻结与RTC E2E持久化。现有RTC e2e_missing_reason仍source_end_clock_unavailable，原UI/APIs不伪造值。
- 尚未验证：新增sender变换的增量延迟、完整弱网/重连、手机/Safari、硬件ADC/声学/AEC、真实语言效果及目标容量；六模型基本单例证据见r85，不扩大为本轮外部调用。

## 下一步关闭条件

1. 用同一个sender worker响应认证capture-clock挑战，保留服务器因果前后锚，不能假定worker/window或client/server同钟。
2. 按已证实RTP→processed区间，仅回填有原始hash/连接/时间证据的真实PCM范围；缺包/跨来源/歧义保持缺失，不能拿新连接填旧缺口。
3. 在既有候选speech_end_audio_ms对应样本冻结源端区间，和实际播放锚形成有误差边界的范围；同一正式入口验证Final原轮次、API持久化/重启后再关闭RTC指标项。之后做必要新增延迟/设备报告，正式采用仍按D068另行决定。

## 版本、命令与临时数据

依赖锁定Pipecat1.8.1、Python3.13，其他版本见runtime-versions.json与requirements.lock/frontend/package-lock.json。定向命令与日志对应：pytest tests/test_td_rtp_input.py/test_td_rtp_integration.py/test_td_rtp_writer.py/test_td_webrtc_cancel.py；node --test frontend/tests/unit/*.test.js；现有td-rtc-entry.spec.js显式启用RTP_INPUT/RTC_CAPTURE两个断言开关。

本机服务127.0.0.1:8796，正式Vite5182；显式loopback守卫/STUN空，全部推理替身。数据库/测试storage.key/记录音频在/tmp/voiceagent-r86-rtc；原始server/Vite/浏览器日志/tmp/voiceagent-r86-*，白名单副本在本目录。只保留自测必要证据，不把Key/数据库/原始capability URL日志/录音入包。本轮没有厂商调用、提交、推送、部署或冻结原型更改；整体目标仍未完成，不自签独立PASS/C/Gate2。

## 独立增量审查

[preliminary-r86.md](../stage-review/preliminary-r86.md)已由未参与本轮实现的评审完成：独立16后端1.05秒、6相关客户端通过；核对4个不同RTP包/7段匹配、native map→queue边界、PCM字节与cleanup，无新增实现缺陷。全Change仍BLOCKED，不自签C/Gate2。独立报告明确不把最后SSRC拒绝分支前的浏览器结果当重连或新E2E证据。

## 审核输入封装核验

review-package/review-inputs.tar.gz当前983文件，逐hash核验并在/tmp/voiceagent-r86-review-extracted实际新目录解包。该cwd使用同锁定环境执行16项后端通过1.14秒、6相关客户端通过31.96毫秒；没有重新调用厂商/浏览器或声称完整后端全量。包内报告为冻结时点，外层本段及package-check为封装后核验。临时辅助脚本/tmp/td_r86_*.py保留，不提交。
