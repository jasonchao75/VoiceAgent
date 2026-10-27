# 当前唯一场景映射入口（r89）

见[current-scenario-matrix.md](current-scenario-matrix.md)，当前756后端/25客户端、严格RTC冷暖/重启/正式1440/390真实历史与原6返修独立结论。以下仅历史追溯，不代表当前未实现。

# 唯一当前结论：r87（2026-10-26）

见[current-scenario-matrix-r87.md](current-scenario-matrix-r87.md)：22项自测ID→Delta→测试/实际证据/未验证类别。当前全后端739、客户端20、正式RTC源端E2E/Final/历史重启通过；A/B证据r82/r84。以下全部为历史审计，不再表示当前未实现；独立C/Gate2与设备/费用范围不混作核心代码缺口。

当前r86：[RTC来源前置证明](development-20261025-r86/README.md)。新增开发候选输入旁路与原生captureTime同包对应，4包/7段，相关16后端/18客户端及正式RTC组合通过；认证源锚/区间回填/VAD冻结与RTC E2E仍未实现。独立阶段未发现新增缺陷但整体BLOCKED；旧r83的715不是当前新代码全量结果。

最新r85：[六模型真实基本范围与实现证据收敛](development-20261025-r85/README.md)。六单例均通过，8项实现任务按JUnit/源hash审计补勾；真实多场景/重连、RTC源端/采用及设备仍未闭合，非最终独立验收。下文为逐轮历史。

当前r84增量：[B证据矩阵与真实ASR结果](development-20261025-r84/README.md)。研发B本地API/存储矩阵完成；D075新素材Flux英文1连接/18来源事件通过。其余范围与r83阶段BLOCKED仍保留，不自签最终验收。

# 当前增量 r83（2026-10-25）

D-074已落实，发布缓存成功/失败继续组合与实际历史恢复已验证；完整后端715通过、当前客户端14单元/25浏览器通过，详情及严格范围见[当前阶段证据](development-20261025-r83/README.md)。完整B矩阵、RTC源端、真实六模型及设备范围未关闭；不是最终独立验收。下文为历史快照，以r83为最新增量。

# 当前任务证据审计（2026-10-22）

本表区分实现/离线验证与真实厂商/硬件证据。不以单元测试、选项可见或Change门禁通过证明完整功能交付。任务编号以tasks.md为准，M0既有确认不重复。

## r44当前差异审计（优先于下方历史快照）

| 验收契约 | 正式路径／具体回归 | 当前证据及阻塞 |
|---|---|---|
| 缺来源不得被新帧/重连掩盖 | SourceNormalizer→ASRService→CustomTDCoordinator；test_td_asr_events.py::test_unknown_identity_cannot_be_erased_by_unrelated_valid_source_or_reconnect | r43完整681项含此测试；仅fixture，真实六模型/绝对时钟未关闭 |
| 同SDK范围可在截止前恢复 | test_td_asr_events.py::test_soniox_unknown_range_recovers_only_within_the_same_sdk_snapshot_scope；test_td_runtime.py::test_same_snapshot_recovery_before_maximum_keeps_normal_submission | r43通过；不同快照或连接不得借此清缺口 |
| D-061截止后明确报错，无提交/工具 | test_td_runtime.py::test_missing_range_fails_once_at_maximum_without_submitting_or_executing_tools；test_api.py::test_asr_failure_after_transport_close_keeps_failed_history_without_double_close；td-runtime.spec.js source_missing | 核心/API/正式浏览器6.5秒通过；已保留原文且turn_id=null，无第二用户轮 |
| 真实播放时间不伪算 | CallCapture.playback_receipt；test_td_history.py::test_renderer_causal_coordinates_accept_network_reordering_but_reject_impossible_samples | 已能保存实际Worklet坐标；跨服务器/渲染时钟仍未建立，数值null+render_clock_uncorrelated，不能勾M4-4整体 |
| 失败通话无已提交轮也能查看证据 | appendTDHistory正式组件；td-runtime.spec.js missing source evidence场景重开Sessions抽屉 | r43先红后绿；旧会话/逐轮中英/双视口4项r44通过。非真实厂商或RTC证明 |
| RTP任务实际渲染及编号仲裁 | D-060隔离来源/编码/RTP/解码坐标实验，正式SerialAudioOutput目前仅WS | 坐标记录不等于解码样本任务归属；按约定停止，R1 BLOCKED，不能因原音轨取消可用勾PLAY-01/NUM整体 |
| 外部ASR/TTS | D-055/057/059首连接失败后停；D-058首条超时后停 | 修复仅离线，r43新ASR/TTS独立批次授权问题等待答复；不复用旧授权 |

原任务完成标记不变。当前完整后端为r43的681 passed，37.23秒；下方578/611/658等只对各自旧快照有效。构建/类型/门禁通过不替代上表未证明的契约。

## 历史审计快照（2026-10-22起）

| 任务 | 当前结论 | 证据与仍缺范围 |
|---|---|---|
| M1-1 | 实现/本地矩阵完成 | r33正式Catalog目标六模型、会话深复制/冻结及来源能力检查；正式UI来源隐藏/General访问/草稿恢复2项通过，Bot草稿持久/重启已有回归。不是外部兼容通过。 |
| M1-2～3 | 部分，未勾 | 六模型范围fixture/SDK桥接已有测试；历史旧型号参数更正见asr-model-evidence-correction.md。未知身份可靠切分/恢复、跨连接时钟和真实回包未闭环。 |
| M1-4 | 既有完成 | 唯一聚合提交与厂商端点隔离，test_td_authority.py/test_td_runtime.py；不是六模型真实兼容。 |
| M2-1 | 实现/本地矩阵完成 | r31/r32：实际Silero ONNX静音及四参数、PCM采样率/声道/样本完整性；VAD分析中/疑似开口回落/异常取消、实际SDK输入积压及原生callback、实际_watch断流/cleanup通过。真实轻声/噪声/容量仍M5未验证。 |
| M2-2 | 实现/离线完成 | test_td_jev.py、test_td_credentials.py、test_td_timing.py：state/questions、凭证加密/脱敏/endpoint绑定、HTTP错误/非法概率、并发busy/100次预算、融合。r38两条合成英文真实Jev请求成功，实际1.14.0，估算US$0.000031752；不证明语言效果/P95或完整语音联调。 |
| M2-3 | 实现/离线完成 | test_td_timing.py/test_td_runtime.py/test_td_authority.py：独立最长看门狗、Final等待/最短、耗时一次、续说/修订失效、空文本/单次提交，实际SDK/慢Jev回归。真实ASR跨连接时钟仍M1未完成。 |
| M2-4 | 部分，未勾 | 同文/格式变化、迟到旧Final及生产上下文隔离已有SDK测试；本地WS/RTC重答通过。完整RTC任务取消/真实厂商残留仍未闭环。 |
| M2-5 | 离线证据完成 | test_td_response_revision.py/test_td_tool_scope.py/test_td_identifier_pipeline.py：无含义比较调用、首个有效Final替换、成功/进行中/失败工具不自动重放、真实SDK后台调用来源隔离。本项明确为可复现离线证据，不扩大为外部工具效果。 |
| M3-1～4、6 | 核心实现/SDK证据已有，保持未勾 | 严格全输入、受控工具/WPM/代次/提醒/混合修订均有回归；真实模型范围/完整网络组合仍缺，详见r13/r19报告。 |
| M3-5 | 部分，未勾 | WS串行任务/实际AudioWorklet回执及清空组合通过；RTC旧答取消本地浏览器通过，精确逐任务回执/完整编号播放仲裁未接完。 |
| M4-1～2 | 部分，未勾 | 缓存/发布/双单元试听/重启/失败重试本地API证据已有；完整发布后故障浏览器矩阵/厂商组合仍缺。 |
| M4-3～4 | 部分，未勾 | 音频格式/间隔、历史来源版本已接；精确播放时钟/指标和实机AEC尚缺，数值不得伪算。 |
| M4-5～6 | 部分，未勾 | 同一正式路由/组件fixture及本地真实API，旧/新历史中英/响应式/存储恢复已有证据；完整状态/视觉diff/可访问性及B矩阵未完成。 |
| M5-1～5 | 进行中，未勾 | 当前报告如实记录自测，不等于完整计划已执行。真实六模型/Jev/TTS需单批授权，实机/目标环境仍缺。 |
| M6 | 未开始 | 未申请独立审核/未自填PASS，不进入User Gate2、主规格合并/归档。 |

本轮M2定向复跑：**64 passed，1.98秒，2依赖弃用警告**，见[日志](development-20261022-r22/m2-task-audit.txt)。源测试位于仓库tests/；完整后端最近r19为578通过。当前任务勾选仅限表中确有实现/离线证据的三个子任务，不宣称里程碑完成。

## r30增量（不修改原任务完成边界）

六模型已有可靠身份的缺时间/非法范围、同来源恢复与多行快照原子性已接正式normalizer/协调器，80项相关回归；完整后端611通过（34.56秒、3依赖弃用警告），见development-20261022-r30/。完全未知身份/跨连接恢复仍未闭环，M1-1～3继续未勾。此前r19/r22的数字为对应轮次历史证据，不是当前完整后端计数。

## 当前交付入口（r39）

以tasks顶部R1/R2/R3及delivery-status.delivery_milestones为准。r39本地SDK/Opus/RTP任务映射前置关口NOT PROVEN，按D-054停止；不作为浏览器组合通过或所有RTP方案不可行。真实厂商素材已定hash，批次仍未授权且费率/守卫待核实。历史数字只对应各自轮次，不重复统计为本轮通过数。

## r40阻塞闭环

| 场景 | 当前证据 | 尚缺/不扩大范围 |
|---|---|---|
| ASR-01/02 尾部重分词 | Soniox实际SDK list→ASRService完整快照标记→normalizer撤销→ledger；原始增量不删除来源，99项相关通过 | 六模型真实兼容、未知身份/重连仍M1/R2 |
| PLAY-01/NUM-01～04 | 同一正式WS页面/真实API/永久缓存/SDK清空/Worklet实际回执：收集、续说保留、提问、清空停旧代次完整组合通过 | 不是RTC/厂商语义/物理设备；其他场景仍依既有SDK矩阵，不称所有网络组合通过 |
| HISTORY-01 | 矛盾采样拒绝、乱序可接、迟到只归原turn、真实渲染但未跨钟原因正确；19项与实际WS历史通过 | 数值播放/端到端仍null，未做跨钟/硬件伪推算 |
| UI-01 A/B | 正式组件对冻结HTML五状态×双视口样式/尺寸/无溢出一致；B保存/缓存/失败/隔离/语言和真实重启通过 | A仍2失败，唯一控件差异Q-044未确认；完整A/C和最终视觉审核不填PASS |
| R2脚本与授权 | ASR9连接、TTS3文本35字符精确计划/守卫；TTS独立导入新进程修复通过 | 新增费用授权未取得，未执行厂商调用 |

最近全量658项是本轮TTS注解导入修复前快照；修复后独立入口/工厂/合成13项通过。最终整包回归待候选冻结，不拼接数字冒充一次全量。

## r41最终增量（2026-10-23）

D-055/057/059三次Flux单连接分别失败停止，前者定位重叠词、后者定位ULP舍入越界；两项离线修复后102项相关通过，未重新真实验证。D-058 TTS首条超时后整批停；上游错误漏接已离线修复但未证明真实原因。D-060隔离映射已记录实际来源/原编码PTS/RTP hash/解码坐标，只证明坐标、不证明真实任务渲染，按停止条件未运行Final/编号/手机/延迟。R1仍BLOCKED，不改正式播放架构。D-056关闭Q-044，正式双视口六状态对照2通过；其他UI/指标/来源/真实兼容范围保留未完成。详见最新self-test-report及development-20261023-r41证据，不以历史通过数冒充最终整包。

## r45 CACHE-02／HISTORY-01增量

正式Web测试发布后旧资源读失败→一次SDK补合成→实际Worklet开播/清空停止→持久化中英历史通过（10.2秒）。修复资源事件/恢复路径漏显与资源耗时误标静音。此为草稿Web测试，版本null如实显示，不能证明公开RTC发布入口；M4整体不勾。证据development-20261023-r45/cache-history-final.txt与ws-identifier-combination.json。

## r46 ASR-03增量

SourceOwnedASRMixin→ASRService→CustomTDCoordinator：test_unbound_callback_never_borrows_the_current_connection_epoch及test_unknown_connection_keeps_raw_text_and_fails_at_existing_deadline先红后绿，覆盖未知原文/空连接归属、重连正常帧不清缺口及D-061失败。原接收任务/SDK重试/native均回归；完整后端683通过（36.82秒）。未证明真实六模型回调或绝对音频时钟。
