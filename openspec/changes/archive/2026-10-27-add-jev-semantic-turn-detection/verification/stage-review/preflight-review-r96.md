# r96两项夹具返修后的当前限定预检（2026-10-26）

**限定结论：两项原预检缺口已修，支持Resolved；当前无新增确认阻塞，可提交精确本批授权申请。不是执行许可，也不签全Change PASS、完整C或User Gate2。** 下方首次BLOCKED原文完整保留历史，不再表示当前未修。

- `require_old_identity`在old_terminal置位之前验证首SpeechStarted身份，缺/空/错误id调用fail并抛错；不再用任意SpeechMetadata开启第二Speak边界。
- `stop_owned_connections`只处理本批捕获的连接列表；真实transport直接abort，替身close有1秒界。夹具stop端点仅loopback来源且Origin完全等于固定本机origin，先置stopped；registry/connect/session/Speak停止后拒绝重开。浏览器从start起try/finally有界POST该端点并关页，原失败保留，cleanup失败也记录为测试失败。不是改停旧服务或其他会话。
- 独立仅重跑当前7项定向：**7 passed /1依赖警告/0.02s**；3种坏metadata身份和只关闭owned连接是4项新增负例。日志r96-independent/fixture-tests-fixed.txt。未扩矩阵、未执行厂商/浏览器/Docker或全量。
- 只读wire-repaired正常5.7秒结果，包含实际Worklet evidence_source与非空同clock断言；旧任务positive stop后新任务start，范围一致。wire-failure故意断言失败后的状态为stopped=true/1连接/1会话/**1Speak**，没有继续第二付费文本；原intentional-local-failure保留。新来源断言不再仅是读旧证据，研发本轮已实际执行。

两项可关闭，但wire仍替身、非真实厂商；没有费用授权不执行--execute。本次预检允许向用户提交新196字符/连接次数/期限/预算/停止条件的独立申请，不复用D-084。未来真实provider若已先完成，需匹配旧speech身份的终止记录与客户端实际停止分列，不伪称真实生成在途取消。

---

# r96 浏览器＋TTS专项夹具独立预检（2026-10-26）

**Result: BLOCKED（两项新夹具边界待修）。** 不签全Change PASS、完整C或User Gate2；本批真实TTS未授权，不执行外部。生产src/frontend实现未参与本次修改，发现项属于新专项夹具/测试，不重新打开旧产品六项缺陷。

按change-verifier只读审查tests/ui/td_tts_browser_app.py、tests/test_td_tts_browser_fixture.py、frontend/tests/ui/td-tts-browser.spec.js和wire-first证据；评审没有改实现/测试、启动厂商/Docker/旧服务或重跑全量，仅执行获准3项离线单测。

## 确认缺口

### P2：R96-METADATA-IDENTITY

`BoundedRegistry.create.observed_message`在收到SpeechMetadata且speak_attempts==1时直接设置old_terminal=true，没有验证该metadata的speech_id等于首个SpeechStarted。后续guarded_send允许old_terminal或cancel_ack任一满足即发第二Speak。于是缺失/错误speech_id的旧完成消息可被错误当作取消边界，违反计划“首身份异常停、旧结束需有证据”的要求。

这是静态控制流确认，不声称真实厂商已经回错，也不表示当前wire-first正常路径失败。最小修复：对完成边界匹配首speech身份；缺失/不匹配失败即停，不能用任意metadata放行。补一个准确的离线错误身份场景，不需费用或扩大测试矩阵。

### P2：R96-FAILURE-TEARDOWN

浏览器测试启动会话后各轮poll/断言/截图均无try/finally；若task_stopped/task_finished缺失、API拒绝或后续断言失败，只有Playwright最终上下文销毁及夹具连接定时截止兜底，没有显式有界“本批失败立即停”动作。25秒deadline限制总连接时间，但不等于首失败即停；不能借正常用例通过证明异常收尾已闭环。

最小修复：finally对当前本批已知会话/夹具连接做有界取消/关闭，保留原失败，不改停其他会话；若页面/媒体损坏仍有可靠停机通道。验证失败注入可用本地wire，不运行真实TTS或已消费批次。

以上已登记delivery-status并向用户披露，待研发修复再交预检，不代修代码。

## 目前相符的防护与证据

- 计划独立于已消费r95授权，196字符/1连接最多2Speak、固定voice/采样率/编码/速度、30秒预算和最多1会话，不发ASR/Jev/LLM/音频数据给外部。main先核授权/hash、独占claim并标started_no_replay再读Key，wire模式不用真实Key；本批未来授权尚未获得，不允许运行--execute。
- 出站仅loopback，或vendor连接任务ContextVar能力下的固定已解析地址/443/TCP；URL主机/path/model/sample_rate/encoding检查、ConnectionBudget实际握手前计数，UDP能力被拒。5秒握手预算+成功连接25秒abort不声称无限等待。缺render证据的首错停止仍须上面finally补齐。
- 正式根页面/既有API/SDK/SerialAudioOutput/Worklet复用，只有vendor socket、ASR/VAD/Jev/LLM为替身。Final gate在真实API接受204、task_started且rendered_samples>0后才释放，存在明确先渲染旧回答再触发固定Final的因果链；未造静态验收页。
- wire-first历史一次td_commit、一次response_restart；旧response1:1实播后task_stopped 12032样本、render_frame91520；新1:2 start128样本、frame91776，同24kHz/同非空clock/evidence_source=audio_worklet_render，未把旧task_finished当取消。全部客户端回执204，无pageerror；probe状态1连接/2Speak/1会话、两个身份hash不同且render_gate_released=true。
- 新增非空clock/evidence_source断言尚未重新运行时，保存证据自身满足该条件；必须分开“读取旧证据成立”与“新增断言在最终源码执行过”。

独立仅`pytest -q tests/test_td_tts_browser_fixture.py`：**3 passed /1依赖警告/0.01s**，见r96-independent/fixture-tests-first.txt。它们证明dry/未授权不读Key、任务能力/目的地、UDP拒绝；没有覆盖上述metadata身份与失败finally。没有厂商调用。

## 限定范围

本次已成功的浏览器组合是**local-real正式SDK/HTTP/WS/浏览器Worklet + wire-fixture vendor**，不是external-real TTS或物理声音，也不是RTC/实时ASR+Jev/真实LLM工具。将来厂商若已先合成结束，只有匹配旧speech身份的终止证明加真实客户端停止，才能按新计划接受；应分别记录provider终态与客户端停止，不伪称仍在厂商生成或真实SpeechInterrupted已触发。

修复两项之后只需定向复核新边界与本机wire路径。即便预检关闭也不授权真实调用；任何新批次仍需精确数据/厂商/次数/费用/停止条件的新用户批准。
