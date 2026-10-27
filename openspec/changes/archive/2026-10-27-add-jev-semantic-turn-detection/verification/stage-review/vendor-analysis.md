# ASR/TTS逐批归因与关闭条件

本分析只使用已保存日志、锁定SDK源与已有离线结果；本轮没有发起外部调用或重新跑业务测试。`status=transcript_or_range_missing`和`synthesis_or_format_error`是探针汇总分类，**不是厂商根因**。下列“确认”均限定到对应证据层。

## 1．真实ASR日志：不是所有失败都意味着没有时间戳

| 决策/结果 | 可确认事实 | 分类与不能确认的事 | 已做/待做 |
|---|---|---|---|
| D-055：原9例首例失败即停 | 收到转写，归一化失败；日志没有足够原始白名单时间 | 不能从旧日志唯一归因厂商缺字段还是解析条件。早期探针未在首坏事件即时停输入，也未留足诊断字段 | 探针停止/白名单记录已离线修复。原记录保留，不回填时间，不重跑该授权 |
| D-057：定位首坏事件 | `I` [0,.08]、`was` [0,.56]起点相同、区间重叠，真实文字和范围存在 | 原校验要求相邻词区间互不重叠，和已观察到的实际回包不相容；是解析假设错误。重叠不等于来源缺失，但跨TD提交若切中重叠词仍不能猜切分 | 已允许起点有序的重叠并保留原值；跨提交词边界仍拒绝。r41 flux-overlap-red/green |
| D-059：独立确认遇下一个边界 | 前15事件恢复，第16词end=4.5600000000000005、窗口end=4.56 | 双精度表示差导致严格比较误拒；不是实际缺词时间 | 已仅容纳4 ULP机器表示噪声，未夹断原值；r41 flux-roundoff-red/green及102相关通过 |
| D-062 continuation：成功 | 29个来源事件都有效，最终EndOfTurn/Final存在；1连接12.106秒 | **该文件/Flux英文/这一连接的范围兼容通过**，不能据此证明六模型、重连、识别质量或完整语义流水线 | 不重复同例找通过数量 |
| D-062 digits：第二例失败后停止 | 前6事件有效，第7包含完整文字/词时间，window_end=2.6399999、最后word.end=2.64，差1e-7秒（0.1微秒） | 输入字段存在，归一化包含校验拒绝，**不是已证实的厂商响应缺失**。该差大于已修4 ULP，不应把前次修复说成覆盖它。日志是SDK交给正式frame的字典，不是完整wire抓包；窗口/词时间的厂商舍入规则与数值来源尚未唯一确定 | 当前尚未修复；后7例未执行、无重试。需下面的离线算法审查后才申请单例确认 |

定位路径：`src/asr/factory.py::_SourceAwareFluxSTTService._handle_turn_info`保留Update字典；`ASRService.normalize_source_frame`→`SourceNormalizer.normalize`→`SourceSegment.__post_init__`检查词是否落在来源范围；`_strictly_before`目前仅4 ULP。探针Sink记录`normalizer.missing_reason`，并在首缺口结束。该链说明为何完整文本仍可能被汇总标成range missing。

证据：
- [D-055](../development-20261023-r41/deepgram-asr-results.jsonl)、[D-057](../development-20261023-r41/deepgram-range-diagnostic.jsonl)、[D-059](../development-20261023-r41/deepgram-overlap-confirmation.jsonl)。
- [D-062完整安全日志](../development-20261023-r47/deepgram-td-asr-synthetic-v1-D-062.jsonl)。
- r41相关修复与r46完整后端683项包含这些既有回归；后者早于r47单元TTS文本修复，不能当最终候选全量。

### 当前ASR最小离线工作（不新增产品规则）

1. 以已保存第7事件复现现有拒绝，连同已通过前6事件与前批重叠/ULP输入作为现有验收回放，不再制造随机批次。
2. 明确真实采样率与来源时钟；审查**映射到同一物理采样边界**能否在不改写原始数值的条件下比较。必须写出端点/取整方向和误差边界，验证跨样本真实越界仍拒绝、跨提交重叠仍不可猜切。
3. 这只是待审工程候选，不是已采用的容差规则。不把供应商窗口随意扩到words包络，不统一加1ms容差，不把输入到达时刻当来源时间。若证明不了，保持缺口并按D-061失败，不以“兼容”名义放宽真实性契约。
4. 只有上述闭环后才提出新的最小外部确认：已冻结digits 5.1675秒+3秒静音、Flux英文、最多1连接≤30秒、无重连/重试、首异常停止，精确hash/费用上限另列授权。本报告未申请、更未执行该调用。

## 2．真实TTS日志：已连接不等于已经发出有效合成

| 决策/结果 | 可确认事实 | 根因等级 | 已做/待做 |
|---|---|---|---|
| D-058 one超时，后2例不运行 | 1连接、15秒合成时限，含关闭约16.19秒；无音频。旧日志未保存协议阶段 | **真实根因未确认**。没有证据将其定为权限、厂商故障或与D-063同因；这些只能是假设 | SDK上游错误原未被下游sink捕获，已补`on_pipeline_error`；慢setup内部20秒清理已对齐显式时限，12项离线SDK回归。不倒推旧失败已解释 |
| D-063 one失败，后2例不运行 | 1连接2.149秒；`connection_opened=true`、incoming=[Connected]、outgoing=[Flush]、audio_bytes=0 | 可排除“连WebSocket都没建立”作为本次唯一解释。**没有已成功发送Speak的记录**，也无SpeechMetadata；不能保证服务端未收到任何收费请求、不能据此报告零扣费 | 不追加网络诊断。结合以下同SDK离线复现处理已确认集成缺陷；真实修复后仍未验证 |
| 同锁定SDK完整离线路径 | sentence模式把one变成one加尾空格；精确Speak守卫抛Text scope mismatch，未把不同文本发给替身socket | **已确认的本地SDK/单元文本与测试授权守卫冲突**。守卫正确保护35字符和精确文本，不能移除守卫。其与D-063现象相符，但真实日志缺被拒阶段字段，不能宣称已排除其他原因 | 单元实例关闭`_append_trailing_space`；普通回复句子分隔不改。实际SDK→renderer→guard→假socket→PCM/SpeechMetadata全路径20相关通过 |

修复位置：`src/tts/unit_synthesis.py::synthesize_unit`；锁定Pipecat1.8.1 `services/deepgram/flux/tts_base.py`构造设置`append_trailing_space=True`，父`TTSService._prepare_text_for_tts`在sentence模式追加空格；`probe_td_tts.py::speak_guard`严格比较授权文本。此处是可复现的集成/探针约束冲突，不是厂商已确认拒绝该音色。

证据：[D-058](../development-20261023-r41/deepgram-tts-results.jsonl)、[D-063](../development-20261023-r47/deepgram-td-tts-synthetic-v1-D-063.jsonl)、[SDK红灯](../development-20261023-r47/tts-exact-text-red.txt)、[20相关通过](../development-20261023-r47/tts-exact-text-final.txt)。回归`tests/test_td_tts_vendor_probe.py::test_actual_sdk_single_unit_preserves_exact_authorized_text`确认实际发送one、3个替身usage字符、480 PCM样本；这些是mock协议结果，不是真实账单或真实音质。

### 测试脚本问题，不能冒充产品缺陷或通过

- 首次定位ASR探针留证不足、停输入不够即时：后续已修，但不能从缺字段旧日志造出原始时间。
- TTS修复后一次离线测试仍失败，因为pytest临时目录在仓库外，`audio_path.relative_to(ROOT)`失败；测试把探针ROOT绑定该临时根后通过，生产路径规则没有被放宽。`tts-exact-text-green.txt`保留失败，最终看`tts-exact-text-final.txt`。
- 探针`status=ok`只说明该ASR例观察到文本/有效来源且无已捕获错误；不是完整TD、取消、准确率或重连通过。D-062第一例的Final已另外核对日志存在，不能把一般汇总ok扩大解释。
- TTS outgoing只在send成功返回后记录；没有Speak记录不等于网络绝对没有任何字节，也不能凭空推算计费。不能把`connection_failure`缺失解释为厂商确认成功。

## 3．为什么现在不再申请同类收费重跑

ASR边界算法仍待离线证明，TTS虽有本地修复但真实失败阶段尚非唯一确认。先让评审检查现有回包/SDK路径、精确文本和终态处理；满足关闭条件后，才另提交“失败digits一条／one一条”的最小批次，不重跑已通过continuation或整9例来碰运气。每项新授权必须独立记录，D-055/057/058/059/062/063都已停止且不得复用。

其他五个ASR目标模型、真实重连、其他语言/真人/噪声、TTS音质与实际取消残留均是**未验证**，不是当前已经定位为失败的厂商问题。现有合成音识别偏差单独报告，不能从小样本给总体WER/P95结论。
