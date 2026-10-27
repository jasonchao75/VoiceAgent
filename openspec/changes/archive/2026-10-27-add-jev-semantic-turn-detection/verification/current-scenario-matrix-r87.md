# 当前r88返修覆盖（2026-10-26）

以下22ID为r87映射基底；当前软件结果更新为r88完整754后端/25客户端，实际命令及逐缺陷证据见[r88](development-20261026-r88/README.md)。ASR-01/03、TIME-02、REV-01/02/03新增正式test_td_review_regressions.py、test_td_transcript.py/test_td_runtime.py/test_td_timing.py；PLAY-01新增test_td_serial_output.py和td-playback-receipts/td-rtc-entry单元及正式HTTP故障/正常播放；UI-01新增完整性关闭/启用/null/刷新1440/390。HISTORY-01当前RTC严格E2E红灯，缺失保持缺失；r87旧成功不代表当前稳定覆盖。r85外部单例不代表本轮新源码已重新真实调用。

# 当前22项自测／Delta场景证据矩阵（r87，2026-10-26）

取代task-evidence-matrix.md中的过时“当前”段；历史失败和旧报告保留，不代表当前源码。后端路径均在tests/，浏览器路径均在frontend/tests/ui/。r87完整739包含这些后端套件；浏览器不声称本轮重跑所有旧矩阵，沿用未改UI/对应实际证据。具体Delta契约列直接取自已确认自测计划。

| ID / Delta契约 | 实际测试 | 结果证据 | 当前结论/未验证 |
|---|---|---|---|
| ASR-01 / Transcript stability；Repeated partial update | test_td_transcript.py; test_td_source_frames.py | [r87/backend-full.txt](development-20261025-r87/backend-full.txt) | 本地SDK/fixture通过；真实多场景修订未测 |
| ASR-02 / Transcript stability；Explain speed evaluation | test_td_asr_events.py; test_td_vendor_probe.py | [r85/six-model-basic-compatibility.json](development-20261025-r85/six-model-basic-compatibility.json) | 六模型external-real基本范围通过；真实WPM/多语言未测 |
| ASR-03 / Single turn authority；Transcript stability | test_td_asr_events.py; test_td_authority.py; test_td_runtime.py | [r87/backend-full.txt](development-20261025-r87/backend-full.txt) | 跨提交/代次/迟到本地通过；实际断线重连/跨连接绝对钟未测 |
| TIME-01 / Bounded silence；Configurable final transcript wait | test_td_timing.py; test_td_runtime.py | [r87/backend-full.txt](development-20261025-r87/backend-full.txt) | 边界/Final窗口SDK通过 |
| TIME-02 / Speech resumes；Transcript revision | test_td_authority.py; test_td_runtime.py | [r87/backend-full.txt](development-20261025-r87/backend-full.txt) | 续说/取消/旧候选SDK通过 |
| TIME-03 / Candidate pause；Session termination及主规格 | test_td_runtime.py; test_api.py; td-runtime.spec.js | [r43/source-failure-network-final.txt](development-20261023-r43/source-failure-network-final.txt); [r87/backend-full.txt](development-20261025-r87/backend-full.txt) | D061缺范围Tmax失败/保留文本本地通过；真实断流未测 |
| JEV-01 / Draft semantic waiting fusion preview及当前设计 | test_td_jev.py; test_td_timing.py | [r87/backend-full.txt](development-20261025-r87/backend-full.txt) | 融合/分布/冲突通过；真实校准未测 |
| JEV-02 / Bounded silence；版本要求 | test_td_jev.py; test_td_credentials.py | [r38/external-results.json](development-20261022-r38/external-results.json); [r87/backend-full.txt](development-20261025-r87/backend-full.txt) | 错误mock/SDK通过，真实两文本基本概率通过；P95/效果未测 |
| NUM-01 / Strict local identifier routing；Optional priority echo rules | test_td_identifier_inputs.py; test_td_identifier_rules.py | [r87/backend-full.txt](development-20261025-r87/backend-full.txt) | 中英全输入/WPM/跟读条件SDK通过；真实语速多模型未测 |
| NUM-02 / Controlled identifier tools；Identifier followed by a question | test_td_identifier_pipeline.py; test_td_identifier_tools.py | [r87/backend-full.txt](development-20261025-r87/backend-full.txt) | 整句工具/更正/混合SDK通过；真实LLM工具效果未测 |
| NUM-03 / Controlled identifier tools | test_td_tool_scope.py; test_td_identifier_tools.py | [r87/backend-full.txt](development-20261025-r87/backend-full.txt) | 幂等/过期/失败SDK通过 |
| NUM-04 / Number collection completeness；New collection after success | test_td_identifier.py; test_td_identifier_rules.py; test_td_identifier_output.py | [r87/backend-full.txt](development-20261025-r87/backend-full.txt) | 状态/计时/修订SDK通过；WS/RTC组合见r69/r83 |
| PLAY-01 / Confirmed playback arbitration | test_td_playback.py; test_td_serial_output.py; td-rtc-identifier-entry.spec.js | [r69/README.md](development-20261025-r69/README.md); [r83/README.md](development-20261025-r83/README.md); [r87/rtc-formal-final.txt](development-20261025-r87/rtc-formal-final.txt) | WS及受控RTC实播/停止/编号仲裁通过；默认采用/弱网/硬件未测 |
| REV-01 / Controlled response restart after material final revision | test_td_response_revision.py; td-rtc-entry.spec.js | [r87/formal-final-history.json](development-20261025-r87/formal-final-history.json) | D049实际Final取消重答/两响应通过 |
| REV-02 / 同上 | test_td_response_revision.py; test_td_runtime.py | [r87/backend-full.txt](development-20261025-r87/backend-full.txt) | 格式/同义首Final重答、重复旧轮隔离通过，按D049非旧改义门槛 |
| REV-03 / Controlled tools及D-049；研发细则E | test_td_tool_scope.py; test_td_identifier_pipeline.py | [r87/backend-full.txt](development-20261025-r87/backend-full.txt) | 成功工具不重放SDK通过；实际厂商取消残留未测 |
| CACHE-01 / Pre-generated echo audio；Compact vocabulary | test_echo_cache.py; test_echo_api.py; test_echo_synthesis.py | [r83/README.md](development-20261025-r83/README.md); [r87/backend-full.txt](development-20261025-r87/backend-full.txt) | 发布/版本/重复次数/缓存重启本地通过；真实音质未测 |
| CACHE-02 / Runtime echo cache recovery | test_echo_runtime.py; test_td_identifier_output.py; td-rtc-identifier-entry.spec.js | [r83/README.md](development-20261025-r83/README.md); [r87/backend-full.txt](development-20261025-r87/backend-full.txt) | 固定发布配置恢复成功/失败跳过继续本地通过；厂商故障实播未测 |
| HISTORY-01 / Per-turn TD history；D-049与主规格指标 | test_td_history.py; test_rtp_capture_clock.py; td-rtc-entry.spec.js; td-history-real-api.spec.js | [r81/README.md](development-20261025-r81/README.md); [r87/formal-final-history.json](development-20261025-r87/formal-final-history.json); [r87/restart-history-check.json](development-20261025-r87/restart-history-check.json) | 真实WS/受控RTC来源→渲染范围及API重启通过；旧值不回填；硬件/精度未测 |
| PRODUCT-01 / bot-config Delta；voice-session主规格 | test_td_config.py; test_td_credentials.py; td-settings.spec.js; td-asr-source-entry.spec.js | [r84/checkpoint-b-matrix.json](development-20261025-r84/checkpoint-b-matrix.json); [r87/backend-full.txt](development-20261025-r87/backend-full.txt) | 正式API/存储/隔离/脱敏/刷新重启本地通过 |
| UI-01 / Conditional configuration；现有Sessions/Share及项目UI规则 | td-baseline.spec.js; td-validation-states.spec.js; td-history-baseline.spec.js; td-history-recovery.spec.js | [r82/checkpoint-a-matrix.json](development-20261025-r82/checkpoint-a-matrix.json); [r84/checkpoint-b-matrix.json](development-20261025-r84/checkpoint-b-matrix.json) | 正式A/B桌面窄屏中英/错误矩阵通过；独立C及跨浏览器待审核/实测 |
| AUDIO-01 / Jev semantic turn mode；跟读续说规则 | test_pipeline.py; test_td_runtime.py; test_td_rtp_input.py; td-rtc-entry.spec.js | [r87/backend-full.txt](development-20261025-r87/backend-full.txt); [r87/formal-final-history.json](development-20261025-r87/formal-final-history.json) | 格式/VAD/采集→渲染软件证据通过；D045物理耳机外放双讲/轻声噪声/目标容量未验证 |

证据路径中的rNN为verification/development-*-rNN唯一目录；所有引用存在性已核对。严格等级：SDK/fixture、local-real、external-real分列，不互相替代。当前源码清单与运行版本在r87/review-package及README。实际命令和全量结果见r87 README；历史浏览器命令保留各轮日志。独立审查不会自动把上述未验证项变为通过。
