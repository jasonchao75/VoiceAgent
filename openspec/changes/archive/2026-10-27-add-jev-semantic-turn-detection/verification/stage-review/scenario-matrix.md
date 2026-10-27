# Spec→正式实现→测试与证据索引

这是逐Requirement分组、逐Scenario列名的阶段审核索引；代表用例不是该组全部场景的覆盖证明。所有引用已静态核对存在，**本轮未重新运行这些测试**。未实现/失败/未验证见README，边界列优先，不能把测试文件存在当PASS。完整同组断言由评审按模块核查，缺口继续进入tasks。

## 已取得的结果，不拼成一次新全量

| ID | 实际证据 | 范围与限制 |
|---|---|---|
| E1 | r46/backend-full.txt：683 passed，36.82秒，5依赖警告 | 完整本地后端，早于r47单元尾空格修复；不证明厂商/硬件 |
| E2 | r47/D-062 ASR jsonl：continuation29有效事件含Final；digits第7事件失败 | external-real；一条通过一条失败，其他7未运行 |
| E3 | r38/external-results.json：Jev2文本成功 | external-real，仅概率格式/基本连通，不证明语言/P95 |
| E4 | r42/ui-a-final.txt：5 passed，10.1秒；正式六状态中英1440/390 | fixture正式DOM；D-056唯一批准差异，非整体A/C通过 |
| E5 | r44/history-regression.txt：4 passed，2.6秒 | fixture正式历史，旧数值标未验证、语言原文保持、浮层无横溢 |
| E6 | r40正式API/重启/普通WS证据；r43 source-failure-history-ui-green.txt | local-real网络/SQLite/Worklet，厂商是替身；普通Final取消与D-061失败历史 |
| E7 | r45/cache-history-final.txt：1 passed，10.2秒；history-review-final.txt | local-real WS补合成/清空实际停止，中英各352字段保持；草稿不等于公开发布RTC |
| E8 | r46/unbound-source-red.txt→backend-full.txt | 无上下文连接不猜归属、未知原文保留、新连接不掩盖缺口、D-061截止失败 |
| E9 | r47/tts-exact-text-red.txt→tts-exact-text-final.txt：20 passed，1.38秒 | 实际SDK离线socket，精确Speak/PCM；真实D-063失败仍不算已修复联调通过 |

所有目录位于本文件父目录verification，精确路径见evidence-index.json。逐个结果只对当时工作树/范围有效，不能相加成最终全量。

## 分组映射

### 1. Self-developed TD source for every catalog ASR model

- Spec：`openspec/changes/add-jev-semantic-turn-detection/specs/bot-config/spec.md:3`。
- 代表用例：`tests/test_td_config.py::test_every_model_allows_custom_source_without_expanding_off`。
- 覆盖边界：E1/E4；六模型配置可选，不等于真实兼容。
- Scenarios：Select self-developed for any supported ASR。

### 2. Conditional custom TD configuration

- Spec：`openspec/changes/add-jev-semantic-turn-detection/specs/bot-config/spec.md:10`。
- 代表用例：`tests/test_td_config.py::test_td_draft_persists_when_source_hidden_and_restart`。
- 覆盖边界：E1/E4；本地保存/恢复，完整UI仍未签A/B。
- Scenarios：Switch source away and back。

### 3. Existing Sessions and Share visual structure

- Spec：`openspec/changes/add-jev-semantic-turn-detection/specs/bot-config/spec.md:18`。
- 代表用例：`frontend/tests/ui/td-history-evidence.spec.js::formal per-turn history preserves candidates and response versions at 1440px`。
- 覆盖边界：E5；正式Sessions列表/抽屉截图，Share缺完整定向视觉矩阵。
- Scenarios：Inspect sample TD record。

### 4. Per-turn TD history evidence

- Spec：`openspec/changes/add-jev-semantic-turn-detection/specs/bot-config/spec.md:25`。
- 代表用例：`tests/test_td_history.py::test_final_replacement_retains_each_generated_response_with_original_turn_identity`。
- 覆盖边界：E1/E5/E6；跨时钟数值未闭环。
- Scenarios：Resumed speech creates multiple attempts in one turn；Preview normal and legacy conversations。

### 5. Pre-generated echo audio and publish validation

- Spec：`openspec/changes/add-jev-semantic-turn-detection/specs/bot-config/spec.md:36`。
- 代表用例：`tests/test_echo_api.py::test_cache_generate_preview_restart_and_publish_only_check`。
- 覆盖边界：E1/E6；真实TTS失败，试听为本地合成。
- Scenarios：Change playback gap；Publish with missing audio；Prototype without real audio。

### 6. Compact vocabulary audio controls

- Spec：`openspec/changes/add-jev-semantic-turn-detection/specs/bot-config/spec.md:51`。
- 代表用例：`tests/test_echo_cache.py::test_durable_units_deduplicate_generation_but_not_playback`。
- 覆盖边界：E1/E4/E6；正式控件已接，真实音质未验证。
- Scenarios：Multiple aliases share audio。

### 7. Configurable overlength reminder

- Spec：`openspec/changes/add-jev-semantic-turn-detection/specs/bot-config/spec.md:58`。
- 代表用例：`tests/test_td_rule_settings.py::test_explicit_priority_settings_are_frozen_and_serializable`。
- 覆盖边界：E1/E4；运行场景另见identifier_rules/runtime，不以配置测试证明播放。
- Scenarios：Configure distinct reminders。

### 8. Runtime echo cache recovery and fixed echo speed

- Spec：`openspec/changes/add-jev-semantic-turn-detection/specs/bot-config/spec.md:65`。
- 代表用例：`tests/test_echo_runtime.py::test_clear_during_missing_asset_repair_never_reinserts_audio`。
- 覆盖边界：E1/E7；草稿WS恢复已验，公开发布RTC未接。
- Scenarios：Cache unavailable after publication。

### 9. Jev budget requires no product control

- Spec：`openspec/changes/add-jev-semantic-turn-detection/specs/bot-config/spec.md:72`。
- 代表用例：`tests/test_td_config.py::test_jev_budget_is_uniform_without_hidden_ui_field`。
- 覆盖边界：E1/E4；无新控件。
- Scenarios：Create configuration without a hidden budget。

### 10. Jev semantic turn mode

- Spec：`openspec/changes/add-jev-semantic-turn-detection/specs/voice-pipeline/spec.md:5`。
- 代表用例：`tests/test_td_runtime.py::test_runtime_unexpected_jev_error_is_safe_and_falls_back`。
- 覆盖边界：E1/E3；真实Jev仅2文本基本兼容，语言效果/整链未验证。
- Scenarios：Candidate pause。

### 11. Bounded silence and cancellation

- Spec：`openspec/changes/add-jev-semantic-turn-detection/specs/voice-pipeline/spec.md:12`。
- 代表用例：`tests/test_td_timing.py::test_revision_invalidates_semantic_result_but_not_hard_deadline`。
- 覆盖边界：E1；相关整个timing模块含续说/单提交/最终等待，非真实厂商时延。
- Scenarios：Valid result arrives；Speech resumes；Transcript revision；Deadline without semantic result。

### 12. Single turn authority

- Spec：`openspec/changes/add-jev-semantic-turn-detection/specs/voice-pipeline/spec.md:31`。
- 代表用例：`tests/test_td_runtime.py::test_real_pipecat_aggregator_releases_exactly_one_context_after_owned_commit`。
- 覆盖边界：E1；SDK本地单一提交。
- Scenarios：Partial at commit。

### 13. Configurable final transcript wait

- Spec：`openspec/changes/add-jev-semantic-turn-detection/specs/voice-pipeline/spec.md:38`。
- 代表用例：`tests/test_td_timing.py::test_final_wait_begins_after_semantic_target_and_is_bounded`。
- 覆盖边界：E1；模块另含最大截止与latest Partial不重启窗口。
- Scenarios：Final arrives within configured wait；Final wait expires first；Maximum silence expires first。

### 14. Optional priority echo rules

- Spec：`openspec/changes/add-jev-semantic-turn-detection/specs/voice-pipeline/spec.md:53`。
- 代表用例：`tests/test_td_identifier_output.py::test_sent_revision_is_corrected_before_ordinary_without_erasing_original_facts`。
- 覆盖边界：E1/E7；WS本地，RTC仲裁未接。
- Scenarios：Slow variable-length sequence pauses；User continues during echo playback；Repeated partial update。

### 15. Advanced rule configuration and diagnostics

- Spec：`openspec/changes/add-jev-semantic-turn-detection/specs/voice-pipeline/spec.md:68`。
- 代表用例：`tests/test_td_identifier_rules.py::test_business_units_ignore_asr_token_count_and_window_trailing_silence`。
- 覆盖边界：E1/E4；实际厂商WPM时间覆盖未验证。
- Scenarios：Explain speed evaluation；Account for pause elapsed。

### 16. Assistant keyword rule condition

- Spec：`openspec/changes/add-jev-semantic-turn-detection/specs/voice-pipeline/spec.md:79`。
- 代表用例：`tests/test_td_identifier_rules.py::test_keyword_gate_and_full_input_format_are_required_before_collection`。
- 覆盖边界：E1；严格门槛离线。
- Scenarios：Explain assistant keyword match。

### 17. Stable assistant keyword context

- Spec：`openspec/changes/add-jev-semantic-turn-detection/specs/voice-pipeline/spec.md:86`。
- 代表用例：`tests/test_td_runtime.py::test_final_reanswer_keeps_original_input_keyword_gate_and_generation`。
- 覆盖边界：E1；SDK＋编号模块，不证明真实LLM工具遵循率。
- Scenarios：User input is split after one assistant prompt；Echo does not replace collection prompt。

### 18. Jev configuration prototype

- Spec：`openspec/changes/add-jev-semantic-turn-detection/specs/voice-pipeline/spec.md:97`。
- 代表用例：`frontend/tests/ui/td-settings.spec.js::formal Advanced edits and saves explicit TD settings`。
- 覆盖边界：E4；预览/编辑/请求无Key；安全凭证另见test_td_credentials.py。
- Scenarios：Preview request without secret。

### 19. Draft semantic waiting fusion preview

- Spec：`openspec/changes/add-jev-semantic-turn-detection/specs/voice-pipeline/spec.md:105`。
- 代表用例：`tests/test_td_timing.py::test_distribution_fusion_subtracts_elapsed_once`。
- 覆盖边界：E1/E4；825/375例为确定性演示非模型效果。
- Scenarios：Weighted waiting example。

### 20. TD prototype language switching

- Spec：`openspec/changes/add-jev-semantic-turn-detection/specs/voice-pipeline/spec.md:112`。
- 代表用例：`frontend/tests/ui/td-runtime.spec.js::formal language switch changes labels without changing TD request or user values`。
- 覆盖边界：E4/E5/E7；正式语言/请求及原值保持，非完整全状态A/B。
- Scenarios：Switch language without changing request。

### 21. Number collection completeness configuration

- Spec：`openspec/changes/add-jev-semantic-turn-detection/specs/voice-pipeline/spec.md:120`。
- 代表用例：`tests/test_td_identifier.py::test_unfinished_reminder_preserves_and_success_new_start_clears`。
- 覆盖边界：E1/E4；配置＋本地状态，RTC播放未接。
- Scenarios：Target length differs from echo segment size。

### 22. Self-developed source is sole final turn authority

- Spec：`openspec/changes/add-jev-semantic-turn-detection/specs/voice-pipeline/spec.md:128`。
- 代表用例：`tests/test_td_authority.py::test_no_sdk_timer_or_smart_turn_in_custom_aggregator`。
- 覆盖边界：E1；运行时另见stop_strategy测试。
- Scenarios：Provider boundary while self-developed selected。

### 23. Transcript stability is separate from turn ownership

- Spec：`openspec/changes/add-jev-semantic-turn-detection/specs/voice-pipeline/spec.md:135`。
- 代表用例：`tests/test_td_transcript.py::test_provider_turn_crosses_td_commit_without_repeating_prefix`。
- 覆盖边界：E1/E2；真实digits仍失败；流式Update桥见test_td_asr_events。
- Scenarios：Final prefix followed by partial tail；Flux interim update must reach TD；Late final cannot finish newer speech。

### 24. Confirmed collection revision and clear behavior

- Spec：`openspec/changes/add-jev-semantic-turn-detection/specs/voice-pipeline/spec.md:151`。
- 代表用例：`tests/test_td_identifier_output.py::test_collection_clear_invalidates_a_pending_recovery_before_any_audio_is_queued`。
- 覆盖边界：E1/E7；补读、提醒和工具分别见identifier/runtime模块，RTC未接。
- Scenarios：ASR corrects played content；User requests positional correction；Reminder preserves collection。

### 25. Strict local identifier routing

- Spec：`openspec/changes/add-jev-semantic-turn-detection/specs/voice-pipeline/spec.md:166`。
- 代表用例：`tests/test_td_identifier.py::test_mixed_input_is_not_locally_extracted`。
- 覆盖边界：E1/E7；同模块覆盖独立/两位/混合，真实模型范围仍未验证。
- Scenarios：Pure identifier stays local；Prefixed identifier uses conversation path；Mixed control request；Two adjacent identifier units；Filler inside input。

### 26. Controlled identifier tools for mixed input

- Spec：`openspec/changes/add-jev-semantic-turn-detection/specs/voice-pipeline/spec.md:192`。
- 代表用例：`tests/test_td_identifier_pipeline.py::test_real_sdk_identifier_tool_continuation_and_final_share_one_effect`。
- 覆盖边界：E1/E7；工具schema/handler/幂等见identifier_tools，真实LLM语义质量未验证。
- Scenarios：LLM submits normal prefixed identifier；Clear on contrastive correction；Stale or failed tool call；Partial routing changes。

### 27. New collection after success

- Spec：`openspec/changes/add-jev-semantic-turn-detection/specs/voice-pipeline/spec.md:211`。
- 代表用例：`tests/test_td_runtime.py::test_new_pure_input_resets_only_after_committed_final_success`。
- 覆盖边界：E1；受控混合新输入另见test_td_identifier_tools。
- Scenarios：Start another collection after success；Continue an unfinished collection。

### 28. Identifier followed by a question

- Spec：`openspec/changes/add-jev-semantic-turn-detection/specs/voice-pipeline/spec.md:223`。
- 代表用例：`tests/test_td_runtime.py::test_question_after_processed_pure_input_reuses_state_without_resubmitting_digits`。
- 覆盖边界：E1/E7；正式WS清空组合，RTC未接。
- Scenarios：Question after separately handled identifier；Identifier and question in one candidate；Ordinary phrase containing a number word。

### 29. Confirmed playback arbitration

- Spec：`openspec/changes/add-jev-semantic-turn-detection/specs/voice-pipeline/spec.md:240`。
- 代表用例：`tests/test_td_playback.py::test_continuation_preserves_active_echo_but_clear_requires_stop_ack_before_next`。
- 覆盖边界：E1/E7；WS任务渲染通过；RTC为未实现，不是仅未测试。
- Scenarios：Client-confirmed echo start；Clear overrides ordinary echo continuation。

### 30. Controlled response restart on final after partial submission

- Spec：`openspec/changes/add-jev-semantic-turn-detection/specs/voice-pipeline/spec.md:252`。
- 代表用例：`tests/test_td_response_revision.py::test_first_final_always_restarts_submitted_partial`。
- 覆盖边界：E1/E6；D-049首有效Final不判断含义；真实厂商取消残留/完整RTC仍缺。
- Scenarios：Valid final after submitted partial；Final before submission；Duplicate or stale final revision。

### 31. Uniform Jev session request budget

- Spec：`openspec/changes/add-jev-semantic-turn-detection/specs/voice-pipeline/spec.md:268`。
- 代表用例：`tests/test_td_jev.py::test_uniform_100_attempt_budget_includes_failures_and_keeps_watchdog`。
- 覆盖边界：E1；100次含失败，费用授权独立。
- Scenarios：Session exhausts the fixed budget。

### 32. Bounded failure for unavailable ASR source evidence

- Spec：`openspec/changes/add-jev-semantic-turn-detection/specs/voice-pipeline/spec.md:276`。
- 代表用例：`tests/test_td_source_frames.py::test_unknown_connection_keeps_raw_text_and_fails_at_existing_deadline`。
- 覆盖边界：E1/E8；r43正式WS错误/历史闭环，真实厂商恢复仍缺。
- Scenarios：Missing source evidence reaches maximum silence；Proven recovery before the maximum。
