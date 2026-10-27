# r49：阶段提交后的必要W2修复

只处理D-062已确认的ASR边界误拒；无新外部调用、无完整回归、无RTC调查/架构修改。原阶段review-inputs.tar.gz及snapshot.json未覆盖。5个源码/测试文件的增量为delta-from-stage.patch，基线与当前SHA在delta-from-stage.json；评审可审原包和本增量，不把旧全量结论当新代码已全量通过。

## 原因与实现

正式AudioConfig明确16kHz；窗口终点2.6399999秒与词终点2.64秒包含相同PCM样本，ceil对应边界均42240。SourceNormalizer/SourceSegment只从正式factory取得已知率；源/词原始时间不改写、不假设float32、不加固定毫秒容差。未知率保持原严格比较。

SourceSegment边界包含、ledger消费及旧提交Final解析使用同一物理采样范围；不能只使构造通过而在消费时又把同边界误判为切进词。2.6400001秒和2.6400625秒均比该窗口多包含下一样本，仍拒绝；真正跨提交边界的词仍unsplittable。可靠表示之外的样本坐标在构造边界拒绝，不推迟到消费阶段。推导/范围见asr-boundary-design.md。

## 必要验证与实际结果

- pcm-boundary-red.txt：保存的D-062字典经正式factory归一化返回空，是原行为失败；配套ledger测试因缺sample_rate内部参数TypeError，属于缺接口，不当作第二个独立业务缺陷证据。总2 failed/59既有passed。
- pcm-boundary-green.txt：127相关passed，3依赖警告，6.42秒；包含ASR/ledger/runtime/source/探针，不是最终完整回归。
- consumer-regression.txt：补同一例的未知率/真实额外样本拒绝约束并核对编号/工具/重答受影响消费者，50 passed，1警告，0.93秒。不与127相加报独立总数（有重叠）。
- target-final.txt：最后原始payload深副本保持断言及构造坐标合法性补齐后，仅复查上述2个目标用例；没有重复扩同类矩阵。ruff和实际Python3.13三源文件mypy通过。

命令：.venv/bin/pytest tests/test_td_asr_events.py tests/test_td_transcript.py tests/test_td_runtime.py tests/test_td_source_frames.py tests/test_td_vendor_probe.py -q；消费者命令：.venv/bin/pytest tests/test_td_asr_events.py::test_saved_flux_digits_boundary_uses_only_its_known_pcm_sample_extent tests/test_td_transcript.py::test_sample_equivalent_consumed_edge_keeps_final_prefix_and_new_tail_separate tests/test_td_identifier.py tests/test_td_identifier_inputs.py tests/test_td_identifier_rules.py tests/test_td_identifier_output.py tests/test_td_identifier_pipeline.py tests/test_td_response_revision.py tests/test_td_tool_scope.py -q。没有运行pytest全部tests，最终统一回归仍按阶段计划等候选收敛。

## 仍缺与下一步

真实修复后Flux数字单例尚未确认，其余模型/重连仍未验证。先供阶段评审核对本算法与精确单元TTS修复；如果需要外部确认，再单独提交失败digits一条和one一条的最小授权，不借D-062/063余量重跑。RTC Q-046仍未选择，无权推进新播放职责或正式替换。本轮只是H2离线工程原因闭环，不称两个硬阻塞全部解决。
