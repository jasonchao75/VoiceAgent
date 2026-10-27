# 研发自测报告 — 正式WebSocket渲染回执增量

**IN PROGRESS / NOT READY FOR INDEPENDENT REVIEW。** 完整M1—M5未闭环，不申请独立审核/Checkpoint C/User Gate 2。D-050已确认；前一轮预算及基础协议证据见[self-test-report.round10.md](self-test-report.round10.md)。

## 实际实现与验证

- 自建TD正式TTS后插入AudioTaskTagger；同provider上下文音频获得同一不可变任务身份，服务端TTS结束发送同队列task_end。新TTSStarted允许上下文复用但分配新任务；已结束且无新边界的迟到音频拒绝。服务端发送不当成客户端已结束；已发任务保留为停止目标，只有匹配终态回执才回收。
- 自建TD的正式WebSocket选用既有Protobuf专用serializer；客户页仍是原WebSocketTransport/WavMediaManager链路，加入同协议任务名解析和渲染线程worklet。原生/chat路径不启用；没有新增传输、依赖或服务端AEC。
- 工作线程实际写出样本才报task_started，task_end且队列排空才报finished；普通跟读续说不在manager层中断，显式清空可停止。跨渲染节点保留任务封锁，结束后的旧包、先到stop的任务及断线后音频均拒绝。
- 新认证playback-events API仅接受活动会话和服务端已准备任务，禁止文本/未知字段，零样本started拒绝，重复幂等、倒退同类计数拒绝。事实按原response_id记录，不落到当前turn；主线程client elapsed保留独立时钟，数值播放指标保持缺失。
- local-real SDK验证重分块/短尾补齐身份、tagger任务结束和复用；local-real ASGI验证错误token401、未知任务/零开播409、文本422、合法回执204。外部厂商完全替换，无真实/付费调用。
- 真实Chromium AudioWorklet组件测试使用Python正式serializer生成的2400样本PCM：正式decoder与worklet匹配任务开播/2400样本结束；48000样本echo续说不打断，显式stop在0<count<48000时回执；旧包/提前stop/断线拒绝。该测试在正式页面导入生产组件，**不是完整实际WebSocket网络通话**，未使用麦克风/真实听感作为证据。
- 最终全量 **551 passed，3项依赖警告，32.72秒**：[pytest-final](development-20261021-r11/pytest-final.txt)。浏览器2项通过（渲染器＋正式配置），2.5秒；Node quantum fixture2项通过；ruff、mypy相关53源文件、Vite build、JS语法、git diff --check通过。
- 新tagger/任务回执缺失的红灯已保留。旧pipeline测试尾部顺序按新增tagger更新，并明确断言类型/位置；测试漂移不冒充功能缺陷。

## 未完成与未验证

1. 完整WebSocket网络会话/麦克风链路尚未打通离线实测；WebRTC无对应实际任务/渲染映射。串行播放arbiter仍未接，缓存跟读、更正补读、清空与输出全联动仍缺。组件续说/停播证据不替代这些组合场景。
2. 渲染task_failed原因render_queue_limit尚未通过API进入历史，需要补错误原因白名单/回归。当前client_elapsed_ms是主线程收到渲染消息时刻，不能冒充精确quantum或硬件首播；渲染时钟关联/真实数值指标待补。
3. 旧纯编号改混合句完整推理、未知范围/重连音频时钟、正式UI缓存交互/完整状态/真实API刷新重启/中英与视觉diff未闭环；Checkpoint A/B未通过。
4. 真实六模型、Jev/TTS效果/语言/费用/延迟、物理耳机外放/AEC双讲及资源目标未测。没有真实或付费外部请求，不将Gate1/D-050当费用授权。

原型v0.14未改；不填写独立PASS/Gate2，不合并主规格/归档/提交/推送/部署。Vite已停止；frontend/dist和test-results忽略，r11证据保留。跨语言PCM协议fixture为本地生成非客户音频；无麦克风录音/厂商合成资源。临时/tmp/jev-r11-*.txt为追溯副本。浏览器配置回归刷新r9同名截图，不改变冻结baseline。
