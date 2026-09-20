"""Static contract checks for the dependency-free browser application."""

from pathlib import Path

FRONTEND = Path("frontend/src/main.js").read_text(encoding="utf-8")
STYLES = Path("frontend/src/styles.css").read_text(encoding="utf-8")


def test_approved_product_pages_are_present() -> None:
    """Navigation must expose the approved VoiceAgent and Evaluation products."""
    assert 'data-page="settings"' in FRONTEND
    assert 'data-page="sessions"' in FRONTEND
    assert 'data-page="advanced"' in FRONTEND
    assert 'href="/evaluation.html"' in FRONTEND
    assert "ASR Evaluation" in FRONTEND
    assert "Simulate caller turn" not in FRONTEND


def test_component_drawers_and_test_modes_are_present() -> None:
    """The production UI keeps component and test experiences distinct."""
    for required in (
        '["asr", "TRANSCRIBER · ASR"',
        '["llm", "MODEL · LLM"',
        '["tts", "VOICE · TTS"',
        'id="chat-test-tab"',
        'id="web-call-tab"',
        'id="chat-composer"',
        'id="history-type"',
    ):
        assert required in FRONTEND
    assert "[hidden] { display: none !important; }" in STYLES


def test_chat_test_does_not_require_microphone_and_waits_for_ready_transport() -> None:
    """Text testing must bypass device setup and reject stale fake sends."""
    assert 'enableMic: testMode === "web_call"' in FRONTEND
    assert 'if (testMode === "web_call") await client.initDevices();' in FRONTEND
    assert "class OutputOnlyMediaManager extends WavMediaManager" in FRONTEND
    assert 'if (testMode === "chat_test") {' in FRONTEND
    assert "transportOptions.mediaManager = new OutputOnlyMediaManager" in FRONTEND
    assert "if (!client || !clientReady)" in FRONTEND
    assert "clientReady = false;\n  client = undefined;" in FRONTEND
    assert "Chat test is not connected. Start the test and wait until it is ready." in FRONTEND
    assert 'new Error("Connection timed out. End the test and retry.")' in FRONTEND
    assert "confirmUnverifiedReasoning" not in FRONTEND
    assert "This custom model has no verified reasoning-disable profile" not in FRONTEND


def test_session_dates_use_stable_english_format() -> None:
    """Session filters must not inherit a Chinese native date-control locale."""
    assert 'placeholder="YYYY-MM-DD"' in FRONTEND
    assert 'id="history-from" type="date"' not in FRONTEND
    assert 'id="history-to" type="date"' not in FRONTEND


def test_session_drawer_closes_on_page_navigation() -> None:
    """Session recording/details must never cover another product page."""
    assert "if (!elements.historyDialog.hidden) closeHistoryDrawer();" in FRONTEND
    assert '<aside id="history-dialog" class="history-dialog"' in FRONTEND
    assert "event.preventDefault();" in FRONTEND
    assert 'aria-label="Close session details"' in FRONTEND
    assert "elements.historyDialog.hidden = true;" in FRONTEND


def test_session_history_uses_queryable_table_rows() -> None:
    """History follows the approved columnar list rather than stacked cards."""
    assert 'class="history-table-header"' in FRONTEND
    assert 'button.className = "history-row";' in FRONTEND
    assert 'class="history-view">View</span>' in FRONTEND


def test_advanced_settings_are_scoped_to_selected_bot() -> None:
    """Advanced behavior is Bot-specific rather than global configuration."""
    assert 'id="advanced-bot-context"' in FRONTEND
    assert "Bot-specific settings for ${bot.name}." in FRONTEND
    assert "save.disabled = !bot;" in FRONTEND
    assert "workspace.append(advanced);" in FRONTEND
    assert 'document.querySelector(".workspace").hidden = false;' in FRONTEND


def test_metrics_do_not_ship_prototype_sample_values() -> None:
    """Production metric placeholders must not masquerade as measurements."""
    assert "ASR final · 142 ms" not in FRONTEND
    assert "LLM TTFT · 318 ms" not in FRONTEND
    assert "TTS first audio · 176 ms" not in FRONTEND


def test_live_turn_metrics_use_the_complete_server_breakdown() -> None:
    """Chat omits only ASR final while both test modes render all other stages."""
    assert "`/api/sessions/${sessionId}/metrics`" in FRONTEND
    for label in (
        "ASR final",
        "LLM splicing",
        "LLM TTFT",
        "TTS initial",
        "TTS TTFT",
        "playback",
        "e2e latency",
        "reasoning",
    ):
        assert label in FRONTEND
    assert 'if (payload.session_type !== "chat_test")' in FRONTEND
    assert "Server component timings become available in Sessions after End test." not in FRONTEND


def test_starting_a_new_test_clears_the_previous_live_transcript() -> None:
    """Completed content belongs in Sessions and must not leak into a new test."""
    assert "function resetLiveTestView()" in FRONTEND
    assert 'elements.transcript.innerHTML = `<div class="empty-state"' in FRONTEND
    assert 'elements.e2eLatency.textContent = "—";' in FRONTEND
    assert 'elements.synthesisLatency.textContent = "—";' in FRONTEND
    assert "resetLiveTestView();\n  setFormLocked(true);" in FRONTEND


def test_asr_advanced_controls_match_the_approved_prototype() -> None:
    """ASR threshold and boolean controls must keep their approved shapes."""
    assert 'id="bot-asr-eot-threshold" type="range"' in FRONTEND
    assert 'id="bot-asr-eot-threshold-value"' in FRONTEND
    assert 'class="switch-row"><span><b>Profanity filter</b>' in FRONTEND
    assert 'class="switch-row"><span><b>Numerals</b>' in FRONTEND
    assert 'class="readonly-control" aria-label="Audio input PCM 16 kHz"' in FRONTEND


def test_api_key_input_is_independent_from_persistence_choice() -> None:
    """The save toggle controls persistence, not whether keys can be entered."""
    assert '<div id="bot-key-fields">' in FRONTEND
    assert "elements.botKeyFields.hidden = false;" in FRONTEND
    assert "syncDrawerCredentials(button.dataset.component);" in FRONTEND


def test_llm_advanced_matches_the_approved_prototype() -> None:
    """LLM Advanced exposes the persisted request controls and fallback UI."""
    for required in (
        "Provider default · No override",
        'id="bot-llm-max-tokens"',
        'id="bot-llm-request-timeout"',
        'id="bot-llm-temperature" type="range"',
        'id="bot-fallback-script"',
    ):
        assert required in FRONTEND


def test_tts_credentials_and_voice_discovery_follow_provider_rules() -> None:
    """TTS Key order and voice availability must follow the approved prototype."""
    assert "panels.tts.insertBefore(keyFieldset, voiceLabel);" in FRONTEND
    assert "elements.chooseBotVoice.disabled = !available;" in FRONTEND
    assert "elements.voiceDiscoveryKeyField.hidden = true;" in FRONTEND


def test_overlays_never_allow_horizontal_scrolling() -> None:
    """Dialogs and drawers may scroll vertically but must never overflow sideways."""
    assert ".voice-picker-dialog" in STYLES
    assert "overflow-y: auto; overflow-x: hidden;" in STYLES
    assert (
        "dialog,\n.history-dialog,\n.component-drawer { max-width:100vw; overflow-x:hidden; }"
        in STYLES
    )
    assert ".voice-picker-dialog > .dialog-close { right:26px; top:20px; }" in STYLES
    assert "margin: 18px 0 -26px;" in STYLES
