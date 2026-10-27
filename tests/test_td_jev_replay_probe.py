"""Keep the real-Jev replay probe inside an exact authorized request envelope."""

from importlib import import_module

import httpx
import pytest


def probe():
    """Import without credentials, sockets or input mutation."""
    return import_module("scripts.evaluation.probe_td_jev_replay")


def test_dry_run_does_not_read_credentials(monkeypatch):
    """Preparing the fixed two-request manifest must not consume a vendor grant."""
    module = probe()
    monkeypatch.setattr(module, "local_key", lambda: pytest.fail("credential touched"))
    assert module.main([]) == 0
    assert module.main(["--execute", "--authorization-decision", "D-999"]) == 2
    plan = module.build_plan()
    assert plan["max_calls"] == len(plan["requests"]) == 2
    assert plan["asr_calls"] == plan["llm_tts_calls"] == 0
    assert plan["cost_ceiling_usd"] == "0.01"


async def test_real_coordinator_blocks_old_final_deadline_with_valid_later_target():
    """Only HTTP is mocked; production normalization, fusion and clock own submission."""
    calls = []

    def response(request):
        calls.append(request)
        noul, probs = (
            (0.95, {"complete": 1.0, "incomplete": 0.0})
            if len(calls) == 1
            else (0.1, {"complete": 0.0, "incomplete": 1.0})
        )
        return httpx.Response(
            200,
            json={
                "answers": {
                    "yield": {"type": "noul", "noul": noul},
                    "speech_state": {"type": "choice", "probabilities": probs},
                }
            },
        )

    result = await probe().run_replay("inert-fixture-key", transport=httpx.MockTransport(response))
    assert len(calls) == 2
    assert result["d080_longer_wait_observed"] is True
    assert result["old_deadline_commits"] == 0
    assert result["maximum_deadline_commits"] == 1


async def test_first_vendor_error_stops_without_second_request():
    """An invalid first response must not be retried or followed by another paid call."""
    calls = []

    def fail(request):
        calls.append(request)
        return httpx.Response(429)

    result = await probe().run_replay("inert-fixture-key", transport=httpx.MockTransport(fail))
    assert len(calls) == 1
    assert result["status"] == "stopped:http_429"


async def test_maximum_first_target_is_untriggered_and_does_not_call_again():
    """A maximum commit has no old Final window to exercise; report the missing scenario."""
    calls = []

    def maximum(request):
        calls.append(request)
        return httpx.Response(
            200,
            json={
                "answers": {
                    "yield": {"type": "noul", "noul": 0.0},
                    "speech_state": {
                        "type": "choice",
                        "probabilities": {"complete": 1.0, "incomplete": 0.0},
                    },
                }
            },
        )

    result = await probe().run_replay("inert-fixture-key", transport=httpx.MockTransport(maximum))
    assert len(calls) == 1
    assert result["status"] == "stopped:scenario_not_triggered:first_target_maximum"
    assert result["maximum_deadline_commits"] == 1
    assert result["d080_longer_wait_observed"] is False
