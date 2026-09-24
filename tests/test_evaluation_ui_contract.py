"""Static contracts for the Evaluation production runtime."""

from pathlib import Path

RUNTIME = Path("frontend/src/evaluation-runtime.js").read_text(encoding="utf-8")
PAGE = Path("frontend/evaluation.html").read_text(encoding="utf-8")


def test_pass_one_progress_names_conversation_checkpoints_not_generic_items() -> None:
    """Pass 1 progress must explain that its durable items are conversations."""
    assert 'copy("conversation checks", "通对话检查")' in RUNTIME


def test_qwen_saved_bot_detection_covers_workspace_model_studio_hosts() -> None:
    """Cost Settings must reuse Qwen keys saved on workspace-specific hosts."""
    assert "host.endsWith('.maas.aliyuncs.com')" in PAGE
    assert "costKey=isQwenBaseUrl(baseUrl)?'Qwen'" in PAGE


def test_predefined_qwen38_is_registered_before_batch_execution() -> None:
    """The normal non-custom Qwen path must persist the exact tested model identity."""
    assert "isCustom||provider==='Qwen'" in PAGE
    assert "if(provider==='Qwen')body.register_for_evaluation_catalog=true" in PAGE


def test_partial_results_render_safe_asr_failure_diagnostics() -> None:
    """Provider jobs and local Case preparation must have separate diagnostics."""
    assert 'copy("ASR failures", "ASR 失败")' in RUNTIME
    assert 'copy("full call", "完整录音")' in RUNTIME
    assert 'copy("Case preparation failures", "Case 准备失败")' in RUNTIME
    assert "failure.retryable" in RUNTIME
    assert "item.evaluation_asr_failures?.[provider]" in RUNTIME


def test_report_never_hides_long_mapped_turn_candidates_as_legacy_context() -> None:
    """A long target turn remains visible because it is formal PD-061 evidence."""
    assert "Full-call transcript retained as legacy evidence" not in RUNTIME
    assert "整通转写已作为历史证据保留" not in RUNTIME


def test_paused_or_partial_batches_can_finish_with_current_results() -> None:
    """The UI must disclose preservation, exclusion, immutability, and zero provider calls."""
    assert 'copy("Use current results", "使用现有结果结束")' in RUNTIME
    assert "/complete-with-current-results" in RUNTIME
    assert (
        "Completed Pass 2 decisions, submitted reviews, and existing Benchmark samples" in RUNTIME
    )
    assert "does not call ASR or LLM services" in RUNTIME
    assert 'runtime.finishMode === "current_results"' in RUNTIME
    assert 'copy("Final report · partial coverage", "最终报告 · 部分覆盖")' in RUNTIME
    assert 'payload.completion_mode === "current_results"' in RUNTIME
    assert "payload.result_excluded_count" in RUNTIME


def test_running_batches_show_live_request_elapsed_time_without_verbose_history() -> None:
    """Only current work should tick each second; historical rows stay compact."""
    assert "function liveOperationsBlock(batch)" in RUNTIME
    assert 'data-started-at="${safe(operation.started_at)}"' in RUNTIME
    assert 'aria-hidden="true"' in RUNTIME
    assert "runtime.elapsedPoll = window.setInterval(refreshVisibleElapsedTimes, 1000)" in RUNTIME
    assert 'copy("Status sync interrupted", "状态同步中断")' in RUNTIME
    assert "function compactStageSummary(batch)" in RUNTIME
    assert 'copy("failed", "失败")' in RUNTIME
    assert 'copy("succeeded", "成功")' in RUNTIME
    assert "function announceOperationStateChanges(batches)" in RUNTIME
    assert 'document.querySelector("#runtime-operation-status")' in RUNTIME
    assert 'id="runtime-operation-status"' in PAGE
    assert 'role="status"' in PAGE
    assert 'aria-live="polite"' in PAGE
    assert 'id="finish-dialog-warning"' in PAGE
    assert ">00:00</time>" not in RUNTIME
    assert 'stage === "event_alignment"' in RUNTIME
    assert "event_alignment: 3" in RUNTIME
    assert "<b>4 音频与证据对齐</b>" in PAGE
    assert "#page-run .steps .step:nth-child(5) span" in RUNTIME
    assert "<b>6 人工复核</b>" in PAGE


def test_historical_turn_review_is_hidden_while_recalculation_is_pending() -> None:
    """Untrusted Turn candidates must not remain visible during recalculation."""
    assert 'data-review-mode="turn" role="tab" aria-selected="false" hidden' in PAGE
    assert 'data-en="ASR Case review" data-zh="ASR Case 复核"' in PAGE
    assert 'id="historical-turn-quality" hidden' in PAGE
    css = Path("frontend/src/evaluation-runtime.css").read_text(encoding="utf-8")
    assert "#historical-turn-quality" in css
    assert "display: none !important" in css
