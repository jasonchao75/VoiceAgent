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
    """Existing partial-result regions must expose the safe ASR failure contract."""
    assert 'copy("ASR failures", "ASR 失败")' in RUNTIME
    assert 'failure.scope === "full_call_context"' in RUNTIME
    assert "failure.retryable" in RUNTIME
    assert "item.evaluation_asr_failures?.[provider]" in RUNTIME


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
    assert 'id="finish-dialog-warning"' in PAGE
