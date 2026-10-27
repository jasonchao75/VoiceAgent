# 研发自测报告 — 正式WS串行播放与逐轮历史增量

**IN PROGRESS / NOT READY FOR INDEPENDENT REVIEW。** M1—M5及正式UI A/B未闭环，不申请独立审核、Checkpoint C或User Gate 2。最新有效产品决定D-050；100次会话预算不增加控件，不授权本轮付费测试。前轮见[self-test-report.round11.md](self-test-report.round11.md)。

## 实际实现与证据

- 正式自建TD WebSocket加入异步串行输出权；普通TTS、固定缓存跟读、更正补读共用原transport。匹配客户端终态才释放串行槽，服务端EOS不算播完。清空只使旧编号/提醒任务失效、停止旧在播编号，保留独立验证有效的普通确认回复。
- 编号来源暂停满足后才准备缓存音频，修订合并未播版本；共享输入/输出逻辑顺序阻止迟到末段越过已就绪普通回复。SDK组合测试覆盖缓存命中0次再合成、续说保留跟读、清空后等客户端stop才发普通回复，以及拒绝queued任务提前完成回执。
- 旧范围修订、缓存恢复、音频任务与客户端回执固定原turn；开场/提醒绑定speech generation，旧无LLM作用域音频仍拒绝。渲染失败白名单原因进入历史，failed/stopped/finished分别保存，不把失败记成成功完成。
- 保留正式API、Pipecat队列、FastAPIWebsocketTransport和Protobuf的ASGI组合探针发现最终write_audio_frame重建PCM导致任务name丢失。已以专用serializer协程局部身份跨原生writer保留，保留其连接检查/采样率/节拍；并发写入无串号、普通音频不继承任务身份。该探针客户端回执为模拟，**不是浏览器完整网络通话**。
- 历史新增conversation_utterance原turn/response证据：未收到结束帧的Partial回答与Final回答分别保留，仍只计一次用户提交；开场单独记录。正式抽屉已增逐轮组件，按明确身份分组候选和回答版本，无归属事件保持会话级；桌面/窄屏固定fixture回归通过；真实API/重启与完整视觉差异尚未覆盖，不宣称UI A/B通过。
- 正式样式发现并修复遗漏@media导致桌面误用窄屏布局；按冻结700/760px条件恢复，桌面双列先失败后通过，窄屏无横向溢出。未修改冻结原型。
- 最新后端全量 **569 passed，3项依赖弃用警告，31.99秒**：[pytest-final](development-20261021-r12/pytest-final.txt)。ruff通过；相关34源文件mypy通过。全目录mypy仍受既有NumPy类型声明/目标Python3.11兼容问题阻断，失败记录保留；不得声称全目录类型检查通过。
- 真实Chromium正式配置/AudioWorklet组件2项通过，3.4秒；最终正式历史/配置/渲染六项全部通过，4.1秒，见[browser-all-final](development-20261021-r12/browser-all-final.txt)。此前一次服务退出和一次热更新期超时均保留失败日志。Node渲染/历史映射4项通过。前端build/JS语法与diff检查通过，最终本轮变更后继续复测。全部外部推理/合成由离线替代，仅bundled Silero模型本地加载。

## 仍未完成和未验证

1. 完整浏览器WS网络通话/麦克风链路、WebRTC任务/渲染映射未闭环；真实六模型回包、未知范围切分、重连时钟和跨连接覆盖未验证。
2. 客户端elapsed是主线程收到渲染消息时刻，不能冒充精确quantum/硬件首播；真实数值播放/E2E指标仍缺失。Final替换回答的逐版本指标完整性、旧纯编号改混合句的完整推理调度仍待。
3. 正式UI完整状态、中英、缓存交互/错误重试、真实API持久化刷新/重启及完整视觉diff未闭环；Checkpoint A/B未通过。逐轮历史组件的新证据不替代这些检查。
4. 真实Jev/TTS语言效果、P95、费用、耳机外放/AEC双讲及目标环境资源尚未实测。**没有真实客户数据或付费外部请求**，不以Gate1或D-050作为费用授权。

原型v0.14 SHA-256仍为657d49b9abf71c872eeaf7f6ccc0b3dfd96b1e4dc9bcd52bb92f43b0778902b4。不填写独立PASS/Gate2，不合并主规格、归档、提交、推送或部署。证据保留于development-20261021-r12；frontend/dist、test-results忽略，/tmp/jev-r12-*.txt为临时追溯副本；没有真实录音或厂商合成资源。Vite仅本地验证运行，完成后停止。
