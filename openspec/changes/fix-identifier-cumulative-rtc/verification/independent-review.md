# 2026-10-28 原生播放与增量跟读最终独立审核

- 审核者：`native_repair_verifier`，独立于实现Agent；未修改生产代码、未调整需求或代替用户验收。
- 结论：**PASS（限定本轮已确认修复的本地工程交付范围）**。本结论取代本轮首轮BLOCKED；下方2026-10-27历史PASS不作为本轮依据。
- 对照：repair-plan、Delta、design、tasks、决策D-20261028-NATIVE-PLAYBACK / FINAL-CONTENT-RESTART / IMPLEMENT-REPAIR。无页面布局/基线修改，ui_change=false；浏览器验证使用正式路由与生产管线，只替换外部服务。
- 发布仍须以最终提交的全量检查、GitHub CI/CD和公开健康/版本核对为准。PASS不证明真机体验、ASR准确率或300ms目标；用户已明确授权自测/审核后部署并复测。

## 独立复验

1. 直接执行最终代码定向组：`pytest -q tests/test_native_incremental_repair.py tests/test_td_response_revision.py tests/test_td_identifier_pipeline.py tests/test_td_identifier_tools.py tests/test_td_history.py`：**47 passed，1既有依赖弃用警告**；日志`/tmp/voiceagent-native-independent-release.log`。之前两轮独立组15/20/46通过不混作最终数量。
2. 直接执行项目门禁：`python3 scripts/quality/verify_change.py fix-identifier-cumulative-rtc`：**PASS，0 errors / 15 warnings**；日志`/tmp/voiceagent-native-independent-gate-final.log`。警告仍含已披露历史根因/真机/延迟未验证及发布收尾任务，不等同零风险。
3. 独立临时探针：延迟首位cache20ms、第二位1ms、10ms gap时，修复前输出`[gap,2,1]`，来源预留后输出`[1,gap,2]`。复验同文及`号码 1,2,3。`Final均保持编号123、successful=True、只一次工具结果。
4. 独立上下文探针：格式Final原位更新用户条目，保留已有assistant消息，产生0个新inference frames；最终定向组另验证SQLite重开后有效Final正文、submitted_text原提交及单用户记录。

## 发现并阻止、已复验闭环的问题

- NATIVE-INCREMENTAL-UNIT-ORDER：并发异步cache不能决定数字顺序；stream_audio在await前预留来源槽位。
- NATIVE-INCREMENTAL-CANCELLED-RANGE：已取消但未发送及prepare前失效无arbiter task的范围可以重排；新ID避免旧失效任务复活，已发送位置不重播。
- NATIVE-ACTIVE-ECHO-ELIGIBILITY：后续语速/时间证据变化不截断已开始有效单元；清空/真正内容失效仍取消。
- NATIVE-FINAL-HISTORY-EFFECTIVE：Final等价更新主历史有效文本与source_final，保留submitted_text；不新增第二用户记录，SQLite重开回归通过。
- NATIVE-FINAL-MIXED-SUCCESS：Final等价在既有已验证contribution上刷新成功证明，不重新执行业务工具，不为新来源赋予旧授权。
- 另复核native cancellation：阻塞write由wake取消，完成native输出Interruption处理后再启下一任务；不再通过异步下游清理与新writer竞争。挂起writer回归验证顺序屏障。

上述项均已由实现Agent向用户披露，并在delivery-status标记Resolved及记录证据；本审核未发现本轮仍阻塞部署的代码缺陷。

## 读取并交叉核对的开发者证据（不冒认独立执行）

- fixture：历史ASR序列1234→12345→123453→格式Final，旧planner重播、新planner输出123453一次；新增重复/修订/取消/部分发送回归。该序列来自历史记录，不是新ASR结果或人工核定参考答案。
- local-real：用户指定15秒私有音频完整240000 samples经过本地Silero，SHA-256 `891e6026f044c5e96e98b73cce37ff2dc05a10fb84770c31d6a411e38bcdf258`；0外部请求。音频留在私有/tmp目录，不入Git。
- local-real + fixture：正式网站鉴权开启、匿名公共RTC编号入口、主动禁用AudioDecoder/encoded transform，两视口**2 passed**（`/tmp/voiceagent-native-identifier-browser3.log`）。JSON mode=native，真实音轨peak约0.132，clear工具成功、server_send_cancelled、任务客户端回执与映射请求为空；读取的结果来自实际生产路由。
- local-real + fixture：最终代码PC WebSocket麦克风路径及普通native RTC **2 passed**（`/tmp/voiceagent-native-pc-rtc-final.log`），验证Final内容修订、声音频率切换和挂断清理。
- 开发者最后混合成功证明更新后的release全量：**830 passed、9 skipped、6既有依赖警告**，日志`/tmp/voiceagent-native-backend-release.log`，本审核读取其最终结果。前端51单元、build、ruff/mypy检查通过，详见native-repair-self-test.md。
- 初始browser401登录cookie与活动通话未落库轮询失败均保留并解释，后续同条件修正测试后两视口通过，不将初始失败隐藏或当作播放通过。

## 证据边界与剩余范围

**未验证**：真实Android/iOS硬件、AEC/蓝牙/运营商弱网、当前厂商ASR准确率、客户录音人工逐字参考、声学尾音实测时长、300ms停口到可听目标。私有音频VAD回放不证明ASR/端到端跟读识别正确；浏览器本地合成音频不证明真实手机可听体验。默认native路径移除旧逐包匹配/解码/回执故障前置条件，不意味着已查明历史手机丢包首因。客户端任务实际开播/完成指标保持未知，不将服务端消费future伪称听到。

这些范围已在自测报告与delivery-status披露；保持product_acceptance=pending，部署后由用户复测，未代填最终产品验收。

## 本次审阅源码指纹

- `src/pipeline/native_output.py`: `ab6bc184566dac8c76277d3b21a249b766346c49440c180127497f7a158df5aa`
- `src/pipeline/incremental_identifier_output.py`: `6bb2acab17d2bc58570db9b04ed17dd45a8c4f50a9785ec160c13248b823cb60`
- `src/pipeline/response_revision.py`: `4d0a3d0664e8f2ea13a2c1fe6ac960a9a8e0f70cf8ba2d446cdd871fb07330a5`
- `src/pipeline/td_strategies.py`: `d9c1c23c006f60a8cdca6c0e1571c2a5a8098c46d19d8c3eae21c2aba82134e6`
- `src/pipeline/custom_td.py`: `72960752a112f419fd7286681db9c5df80fd034e7844eaa0a2411a2a107206d7`
- `src/pipeline/serial_output.py`: `053a4fe15b7e65145decab35753cbede788a5332880ec4b197fa8f05a142299c`
- `src/pipeline/identifier.py`: `6787a865ef21c27becfebc2e070d1b079baf41282145947fc45e1420bc6d72c6`
- `src/pipeline/identifier_tools.py`: `cd87e125972e834e08e3334737d2535a0f44c84cbcda874c392e1a957da2e5f0`
- `src/history/capture.py`: `dc9df96ad6d11fc543d5a470f046bacb5db5393d36c2d849915c11ed95248122`
- `src/pipeline/voice_agent.py`: `16a1ca0639d73675254224b4505281321e4bb5d8b49cb8ab1474fd9a0cdd91f2`
- `src/api.py`: `aa3dac6b0b7d76a45a9b77ad4ce207d9df21c60123f61338ecfd67a2713114ac`

---

# 独立审核结论

- 日期：2026-10-27
- 结论：**PASS（限定本次两个缺陷的本地工程修复范围）**。
- 审核者：`cumulative_review`，结合另一独立审核者 `rtc_fix_review` 的 RTC 专项结果。审核者未实现修复、未修改需求、未代替用户验收。
- 本轮已具备进入用户授权部署的工程条件；部署成功、真实手机/厂商体验仍需单独验证，不能由本结论推定。

## 对照需求与流程

1. 未提交 LLM 的完整编号来源由本地持有，同来源累计 `12 → 123` 即使合并为单个词，也以最新贡献替换而非追加 `12123`；不再以本地跟读边界切词并终止通话。
2. Partial `12` 在关键词、完整格式、WPM、停顿均满足时已派发跟读，**不等待 Final、不调用 LLM**。累计扩展在续说中只更新/撤销旧待播状态，满足新停顿才派发；未满位超时仍有效。
3. 同范围修订可补读；重复 Final 由原输出去重；已独立处理的纯修订不会混入下一次普通问句。清空代次禁止旧来源回灌。真正提交 LLM 后恢复严格音频边界，不允许整体扩展旧普通回复。
4. 正式默认 `create_app()` 的自建 TD + enabled 编号规则，在 session 返回、transport、输入时钟、pipeline 协议四处使用一致选择，接通既有 IdentifierOutput/RTP 任务播放器。其他模式保留 native；未新增数据通道音频。
5. 初始化失败的播放器资源清理已修复，失败不伪报实际播放。详见 `rtc-review.md`。

## 独立复验

- 本审核者直接运行 `/tmp/voiceagent-r91-py311/bin/python -m pytest -q`：**791 passed、9 skipped**，38.30s。随后复跑最终新增 clear/fence 回归所在两文件：**62 passed**。
- 本审核者直接执行 5 个临时离线 probe：续说不抢跑与提醒、同范围补读、下一问无旧编号污染、LLM 提交后边界保护、清空后旧来源隔离，均通过。详见 `backend-review.md`。
- RTC 独立审核者复跑 42 项 RTC/发布后端测试、3 项 echo API 测试、10 项节点/资源释放测试并给出 PASS，详见 `rtc-review.md`。
- 正式浏览器测试由开发者运行、RTC 独立审核者读取证据复核（不冒认本审核者独立复跑）：开发开关关闭，正式 mobile-demo 路由，**1 passed**；真实本机 RTP/Opus 解码、AudioWorklet 播放回执和 clear 停止，native audio muted。ASR/LLM/TTS 是离线替身。
- 最终 `python3 scripts/quality/verify_change.py fix-identifier-cumulative-rtc`：**PASS，0 errors / 2 warnings**。剩余警告为部署/真实环境未验证及收尾任务未勾选。

## 发现的问题与闭环

审核先后阻止并复验修复：累计扩展在续说时抢跑、续说后未满位提醒丢失、无候选同范围修订漏补读、旧纯修订混入下一问、RTC 初始化异常资源泄漏。当前复验未发现仍阻塞本次本地修复交付的问题。

## 未验证与证据边界

真实手机、扬声器/AEC、弱网、真实 ASR/Jev/LLM/TTS 端到端未测；客户端仍要求 RTCRtpScriptTransform 与 AudioDecoder，不能承诺所有 iOS/Android 浏览器兼容。没有进行收费 API 调用或发送真实客户音频。全量测试的 9 个 skip 不计为通过。部署、CI/CD 和线上健康状态由后续交付记录负责。

本报告不修改 `product_acceptance`，也不宣称 Gate2 的真实体验已重新验收。临时证据位于 `/tmp/voiceagent-cumulative-rtc-evidence/`、`/tmp/identifier_review_*.py`，不提交数据库、录音、凭证或缓存。

## 后续匹配计时专项审核

2026-10-27 `matched_packet_review` 对已匹配包误报缺映射的修复给出限定范围PASS，详见 [matched-packet-review.md](matched-packet-review.md)。不将此专项PASS扩展为生产手机故障唯一归因或用户最终验收。

## 后续静音缺包与关闭清理专项审核

2026-10-27 `matched_packet_review` 对静音范围有序退休、关闭后不重启采样及有界鉴权诊断给出限定范围PASS，见 [packet-silence-review.md](packet-silence-review.md)。不推定生产手机首因已唯一确定或用户验收通过。
