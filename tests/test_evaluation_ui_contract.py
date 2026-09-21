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
