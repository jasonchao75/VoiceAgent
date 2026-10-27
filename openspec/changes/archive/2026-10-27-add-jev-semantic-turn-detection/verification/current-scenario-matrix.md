## r97真实TTS与正式WS浏览器停播增量

D085已消费：1连接2Speak、196字符，真实Flux取消确认匹配旧身份；正式页面旧Worklet实播→Final实际停止2624样本→同clock新开播/结束51840样本，回执均204。见development-20261026-r97。只关闭这一WS/Chromium单例，不证明真实ASR/Jev/LLM整链、RTC、编号真实厂商组合、移动/弱网/声学、其他voice或新增链路延迟。旧stop至新start709.33ms为单次观察间隔。D086用户明确真实LLM工具“先保留未验证。”；非最终范围排除。下列历史快照中的浏览器未测由本限定增量补充，不扩为全产品通过。

## r95真实Flux取消与在途残留隔离

D084真实api.deepgram.com/v2/speak固定flux-alexis-en/24kmonoPCM16两文本：1连接2Speak，SpeechInterrupted匹配首speech，新Speak在确认后；实际19200在途旧字节，取消后旧身份输出0，新49920样本。TTS SDK供应商取消/残留子场景有external-real证据；浏览器/Worklet/物理停播、整条实时ASR/Jev/LLM和其他voice/厂商未验证，不扩大单例。授权已消费，账单实扣未知。证据development-20261026-r95。

## r93 Linux资源与Docker上下文限定证据

D083启动Docker并严格新镜像构建成功；Linuxarm64/Python3.11.17、内核1CPU1GiB/noswap限制下，真实Silero独立静音及正式WS替身冷暖两通通过，无OOM（cgroup峰值约179.2MiB）。队列仅100ms采样不证短暂峰值；仍缺真实厂商/VAD语音同链、RTC/弱网/硬件/并发分布/目标x86及新增链路配对延迟，M5-3不全部勾选。

r92“原四Docker输入缺项”静态判断撤回；实际Docker父目录!过宽，修严格白名单后原生哨兵3红6绿→9绿、标准镜像build成功。见development-20261026-r93/strict，根部旧镜像数据仅历史。未发现真实frontend.env，根.env哨兵一直排除，无镜像push。

## r92 D080限定真实Jev证据

D082实际两次Jev1.14、相同生产normalizer/coordinator/fusion/clock：目标963→1952.5ms，旧Final点0提交、原Tmax1提交。ASR来源是r91第5/15条已录事件，音频时钟人工advance；不计作实时ASR/Jev网络竞争、目标点精确提交、媒体/性能或其他厂商通过。见development-20261026-r92/，新增专项执行器4项离线红绿、Ruff及授权日志可审计；已消费不重放。

## r91补充执行证据（不改变未验证范围）

- 目标解释器：实际Python3.11.15＋requirements.lock，756后端通过、mypy目标3.11检查79源通过、pip check通过；证据development-20261026-r91/。不等于Linux1核1GB容量验证。
- ASR范围/流式修订：D081 Deepgram Flux英文单例实际1连接，26条范围完整事件；Partial“test”修为“cancel my”，继续追加第二句，Final保留not。仅生产ASR工厂/SDK/normalizer external-real；没有执行TD/Jev/LLM/TTS，不证明Partial提交后Final重答、D080真实计时竞争、重连/其他语言/WPM。授权已消费，账单实扣未知。
- 其余已有矩阵和r90独立结论保持；设备/性能/完整厂商专项仍见各计划，不以本次单例关闭整个M5-2/3。

# 当前Spec场景→测试→实际证据（r89，2026-10-26）

主规格与Delta契约来自self-test-plan.md，D049/080覆盖旧表述。后端测试在tests/，浏览器在frontend/tests/ui/。完整当前756后端/25客户端及源码身份见[r89](development-20261026-r89/README.md)，不把旧外部证据冒成当前源码重新实测。A/B复用同正式路由DOM，独立C/Gate2未签。

| ID / Delta契约 | 实际测试 | 实际证据 | 当前结论及未验证 |
|---|---|---|---|
| ASR-01 / Transcript stability；Repeated partial update | test_td_transcript.py / test_td_review_regressions.py / test_td_runtime.py | [r89完整后端](development-20261026-r89/backend-full.txt)、[原3红灯](development-20261026-r88/backend-review-red.txt) | 词边界/原文span/重复修订/子词/数字/CJK软件通过；真实多语效果未测 |
| ASR-02 / Transcript stability；Explain speed evaluation | test_td_asr_events.py / test_td_vendor_probe.py / test_td_rtp_input.py | [六模型历史基本结果](development-20261025-r85/six-model-basic-compatibility.json)、[当前756回归](development-20261026-r89/backend-full.txt) | 英文数字external-real为当时版本；新解析/生命周期离线通过；完整真实WPM/语言/覆盖未测 |
| ASR-03 / Single turn authority；Transcript stability | test_td_runtime.py / test_td_authority.py / test_td_rtp_input.py | [晚到/替换红](development-20261026-r89/late-track-red.txt)、[绿](development-20261026-r89/late-track-green.txt) | 连接代次/跨提交/迟到/缺证据D061本地通过；实际跨厂商重连绝对钟未测 |
| TIME-01 / Bounded silence；Configurable final transcript wait | test_td_timing.py; test_td_runtime.py | [r87/backend-full.txt](development-20261025-r87/backend-full.txt) | 边界/Final窗口SDK通过 |
| TIME-02 / Speech resumes；Transcript revision | test_td_timing.py / test_td_runtime.py / test_td_review_regressions.py | [当前756回归](development-20261026-r89/backend-full.txt)、[D080原红](development-20261026-r88/backend-review-red.txt) | 新有效目标优先旧Final窗，不重启窗口/延长Tmax；续说取消/竞争SDK通过 |
| TIME-03 / Candidate pause；Session termination及主规格 | test_td_runtime.py; test_api.py; td-runtime.spec.js | [r43/source-failure-network-final.txt](development-20261023-r43/source-failure-network-final.txt); [r87/backend-full.txt](development-20261025-r87/backend-full.txt) | D061缺范围Tmax失败/保留文本本地通过；真实断流未测 |
| JEV-01 / Draft semantic waiting fusion preview及当前设计 | test_td_jev.py; test_td_timing.py | [r87/backend-full.txt](development-20261025-r87/backend-full.txt) | 融合/分布/冲突通过；真实校准未测 |
| JEV-02 / Bounded silence；版本要求 | test_td_jev.py; test_td_credentials.py | [r38/external-results.json](development-20261022-r38/external-results.json); [r87/backend-full.txt](development-20261025-r87/backend-full.txt) | 错误mock/SDK通过，真实两文本基本概率通过；P95/效果未测 |
| NUM-01 / Strict local identifier routing；Optional priority echo rules | test_td_identifier_inputs.py; test_td_identifier_rules.py | [r87/backend-full.txt](development-20261025-r87/backend-full.txt) | 中英全输入/WPM/跟读条件SDK通过；真实语速多模型未测 |
| NUM-02 / Controlled identifier tools；Identifier followed by a question | test_td_identifier_pipeline.py; test_td_identifier_tools.py | [r87/backend-full.txt](development-20261025-r87/backend-full.txt) | 整句工具/更正/混合SDK通过；真实LLM工具效果未测 |
| NUM-03 / Controlled identifier tools | test_td_tool_scope.py; test_td_identifier_tools.py | [r87/backend-full.txt](development-20261025-r87/backend-full.txt) | 幂等/过期/失败SDK通过 |
| NUM-04 / Number collection completeness；New collection after success | test_td_identifier.py; test_td_identifier_rules.py; test_td_identifier_output.py | [r87/backend-full.txt](development-20261025-r87/backend-full.txt) | 状态/计时/修订SDK通过；WS/RTC组合见r69/r83 |
| PLAY-01 / Confirmed playback arbitration | test_td_playback.py / test_td_serial_output.py / td-playback-receipts.test.js / td-rtc-entry.spec.js | [实际故障](development-20261026-r88/rtc-fault-evidence/receipt-response-lost-history.json)、[严格暖通话](development-20261026-r89/strict-warm/formal-final-history.json) | WS及开发RTC仲裁/停止/有界失败通过；默认采用、硬件/弱网/厂商残留未测 |
| REV-01 / Controlled response restart after material final revision | test_td_response_revision.py / test_td_runtime.py / td-rtc-entry.spec.js | [严格冷通话](development-20261026-r89/strict-cold/formal-final-history.json) | 首有效Final替换，原轮次1含两个响应，实际旧任务停止/新答通过；无效切片不重答 |
| REV-02 / 同上 | test_td_response_revision.py / test_td_review_regressions.py | [当前756回归](development-20261026-r89/backend-full.txt) | D049格式/同义首Final重答、重复/旧轮隔离；不做含义比较 |
| REV-03 / Controlled tools及D-049；研发细则E | test_td_tool_scope.py; test_td_identifier_pipeline.py | [r87/backend-full.txt](development-20261025-r87/backend-full.txt) | 成功工具不重放SDK通过；r95/r97仅Flux SDK/WS浏览器单例，真实LLM工具/其他厂商/设备组合未测 |
| CACHE-01 / Pre-generated echo audio；Compact vocabulary | test_echo_cache.py; test_echo_api.py; test_echo_synthesis.py | [r83/README.md](development-20261025-r83/README.md); [r87/backend-full.txt](development-20261025-r87/backend-full.txt) | 发布/版本/重复次数/缓存重启本地通过；真实音质未测 |
| CACHE-02 / Runtime echo cache recovery | test_echo_runtime.py; test_td_identifier_output.py; td-rtc-identifier-entry.spec.js | [r83/README.md](development-20261025-r83/README.md); [r87/backend-full.txt](development-20261025-r87/backend-full.txt) | 固定发布配置恢复成功/失败跳过继续本地通过；厂商故障实播未测 |
| HISTORY-01 / Per-turn TD history；D-049与主规格指标 | test_td_history.py / test_rtp_capture_clock.py / td-rtc-entry.spec.js / td-history-real-api.spec.js | [两通重启](development-20261026-r89/restart-history-check.json)、[实际历史UI](development-20261026-r89/history-real-api.txt) | 当前WS及开发RTC来源→渲染保守范围/原轮次与响应版本/不伪值/持久化通过；误差宽，声学/精确性能/错误遥测送达未测 |
| PRODUCT-01 / bot-config Delta；voice-session主规格 | test_td_config.py; test_td_credentials.py; td-settings.spec.js; td-asr-source-entry.spec.js | [r84/checkpoint-b-matrix.json](development-20261025-r84/checkpoint-b-matrix.json); [r87/backend-full.txt](development-20261025-r87/backend-full.txt) | 正式API/存储/隔离/脱敏/刷新重启本地通过 |
| UI-01 / Conditional configuration；现有Sessions/Share及项目UI规则 | td-baseline.spec.js / td-validation-states.spec.js / td-settings.spec.js / td-history-real-api.spec.js | [A](development-20261025-r82/checkpoint-a-matrix.json)、[B](development-20261025-r84/checkpoint-b-matrix.json)、[四字段390](development-20261026-r88/ui-390.txt)、[当前历史](development-20261026-r89/history-real-api.txt) | 同正式路由/组件fixture与真实本地API；状态/中英/桌面窄屏/浮层通过，独立C和其他浏览器未验证 |
| AUDIO-01 / Jev semantic turn mode；跟读续说规则 | test_pipeline.py; test_td_runtime.py; test_td_rtp_input.py; td-rtc-entry.spec.js | [r87/backend-full.txt](development-20261025-r87/backend-full.txt); [r87/formal-final-history.json](development-20261025-r87/formal-final-history.json) | 格式/VAD/采集→渲染软件证据通过；D045物理耳机外放双讲/轻声噪声/目标容量未验证 |

上表旧轮次证据只在相应范围复用；r88后src/frontend当前差异为reader及对应测试/fixture，见r89/source-delta-from-r88.json。原生/off/开场/fallback/已有工具/历史回归在最终756中，未用新fixture替代真实厂商或设备。精确实际命令/退出结果/版本与临时路径见r89报告。
