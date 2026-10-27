# 研发自测报告 — TTS回复版本隔离增量

**IN PROGRESS / NOT READY FOR INDEPENDENT REVIEW。** 整体M1—M5未完成，不申请独立审核、Checkpoint C或User Gate 2。缓存/发布与此前编号链路证据见[self-test-report.round6.md](self-test-report.round6.md)。

## 本轮实现与验证

- 正式Flux和ElevenLabs工厂已使用可选作用域服务；自建TD将同一ResponseRevisions权威绑定TTS，原生/chat不启用。未知扩展TTS不支持该协议时明确拒绝，避免静默绕过。
- 在provider context_id生成时绑定原始回复身份；入音频队列和实际向下游输出时分别检查。已取消Partial音频不得改标新Final；新语音轮次也能封锁旧音频。
- 开场/固定话术必须由显式TTSSpeak上下文标记无回复作用域；未知后台上下文拒绝，既不能当开场，也不能借用当前turn。未修改客户端实际播放指标。
- local-real Pipecat PipelineWorker验证了开场音频、Partial合成后Final替换、真实Interruption、迟到provider后台回调被拦、新Final音频带正确身份。仅外部合成生成器为mock；不证明真实厂商网络取消或客户端已停。
- 定向5项作用域测试及正式双TTS工厂绑定通过。全量 **540 passed，3项依赖弃用警告，32.61秒**：[pytest.txt](development-20261021-r7/pytest.txt)。ruff src/tests通过；mypy相关52源文件通过；git diff --check通过。
- 先失败证据包括作用域缺失、未知后台上下文放行和借用当前turn：[r7证据](development-20261021-r7/)。SDK测试曾在切换runner非弃用API时误传list/漏await，已按实际签名修正；夹具错误不作为产品行为红灯。

## 仍未完成 / 未验证

1. 跟读未接正式串行输出；WebSocket/SmallWebRTC任务身份、客户端实际渲染/停止回执仍未完成，已进客户端缓冲音频不能由本次服务端围栏宣称撤回。
2. 旧编号范围跨新输入/提醒的ASR修订和补读、未知范围/重连时间对齐仍未闭环。
3. 正式配置/Jev/词表缓存及完整历史UI、Checkpoint A/B仍未实现；API证据不替代页面验收。
4. 六模型真实回包、Jev/TTS效果/发音/延迟/费用、物理双讲/AEC及资源目标未测。没有外部真实调用，不将Gate1视为费用授权。

冻结v0.14原型未改。未填独立PASS/Gate2，未合并规格、归档、提交、推送或部署。测试PCM/SQLite仅pytest临时目录；r7日志保留，/tmp/jev-r7-*.txt是追溯副本，未暂存提交；无真实录音或付费合成资源、无服务进程。
