# 研发自测报告 — 第三轮增量，整体仍未完成

**IN PROGRESS / NOT READY FOR INDEPENDENT REVIEW。** M1-4已完成；M1其余、M2—M5仍未完整闭环。没有独立审核PASS或User Gate 2。前两轮细节见[self-test-report.round2.md](self-test-report.round2.md)。

## 本轮实际改动及结果

| Spec / 任务 | 实际覆盖 | 结果 / 证据等级 |
|---|---|---|
| ASR-03 / REV-01 | 同一厂商source跨两次TD提交时，尾部快照保存裁剪后范围；迟到Final分别解析原范围，第二轮不恢复旧前缀 | fixture；先失败后通过 |
| REV-03 / M2-5 | 原LLM/TTS速度工具绑定不可变输入上下文；Final重答复用已执行结果，旧轮次拒绝；已发操作即使调用任务取消仍有界结算 | mock/local-real Pipecat；6项作用域/工具测试通过 |
| REV-01/02 | 实际SDK输出生产端拒绝旧回答token和结束帧，防止服务商忽略取消后继续输出 | local-real Pipecat；不证明TTS或浏览器残留取消 |
| NUM-03 / M3-2部分 | submit_identifier/clear_identifier真实SDK schema及handler；后台来源校验，拒绝幻觉值/旧代次，清空后重答不清新数据 | fixture；4项工具测试通过，尚未注册到正式配置驱动流水线 |
| P01—P07、P10—P11 / M3-5部分 | 串行仲裁状态；普通回答跳未播末段、上一段补读优先、清空请求停旧音频、迟到缓存代次失效；未播修订合并；发送未确认状态保留unknown；反向就绪竞争 | fixture；7项仲裁测试通过，尚未接真实音频发送和浏览器回执 |
| HISTORY-01真实性 | 锁定client-js确认BotStartedSpeaking来自服务端消息，移除它触发的虚假first_playback和收到开口即上报audio_stopped，以及按该消息计算的播放时延 | fixture/local-real/static；实际客户端输出证据仍待接，新指标保持缺失，存量值标记unverified，未篡改既有数值 |
| 启动/兼容 | 修复作用域模块触发的循环导入，延迟加载派生LLM服务；原生/chat继续使用原服务 | 完整pytest收集及回归通过 |

## 实跑检查

- 全量pytest：**476 passed，3项依赖弃用警告，31.17秒**。见[pytest.txt](development-20261021-r3/pytest.txt)。
- 正式历史页fixture浏览器2项通过；无横向滚动（1440/390px），截图已查看。ruff src/tests通过；mypy覆盖src/asr、pipeline、llm、session、bots、history、api、publication，共42源文件通过。
- frontend生产构建通过；git diff --check通过。UI构建不等于Checkpoint A/B通过。
- 红灯/绿灯证据见[本轮目录](development-20261021-r3/)。预执行Final竞争、跨提交Final范围、编号工具缺失、播放仲裁缺失及反向就绪顺序均保留失败输出。

## 仍未完成与未验证

1. 编号handler和仲裁器还未接通正式配置/流水线、实际音频发送、播放ID及浏览器开播/停止回执；不能据此标记M3-2/M3-5完成。关键词稳定快照、可靠业务WPM、独立提醒尚未完成。
2. 缓存、固定发布音频、资源指纹、补合成/发布绑定、正式UI/Jev/历史页与Checkpoint A/B尚未完成。
3. 未知音频范围安全消费、真实六模型回包/重连覆盖仍未闭环。fixture不证明真实厂商兼容。
4. 实际LLM/TTS取消、客户端缓冲残留、WebSocket/WebRTC完整路径、耳机/外放双讲AEC、目标1核1GB负载未测。未新增服务端AEC。
5. Jev/TTS/ASR真实调用没有授权，本轮均未执行；真实效果、P95延迟、费用、校准参数未验证。
6. 历史first_playback曾由服务端事件回传；本轮停止产生此伪证据。旧记录来源不明的数值显式标记unverified_client_report，SQLite重启及旧NULL字段兼容通过；缺回执不再声称从未播放。正式历史抽屉1440/390px共2项fixture浏览器测试通过、无横向滚动，截图已人工查看；完整UI A/B仍未完成。

## 工作区、授权和证据

- 基准HEAD仍为2aff076d07599c5352b390edf83106d49e7bb2cb；未提交、推送、部署、合并主规格或归档。
- D-049继续有效：首个匹配Final直接替换当前已提交Partial，不增加语义比较API。
- 冻结v0.14字节未改；本轮SHA检查见证据目录。用户下载脚本、语料、其他Change和报告未覆盖。
- 无真实客户音频/厂商请求/业务库写入；测试仅本地fixture/mock/Pipecat及pytest临时库。
- 本轮证据development-20261021-r3/；临时输出/tmp/jev-*.txt为脱敏测试失败与检查日志，保留追溯，未暂存。frontend/dist及test-results已忽略。
- 尚不申请独立审核；完整实现与M5自测包就绪后交评审Codex，不自行填写独立PASS。
