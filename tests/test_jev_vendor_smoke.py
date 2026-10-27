"""A bounded vendor smoke batch cannot consume a key or call without a matching grant."""

import json
from importlib import import_module

import httpx
import pytest


def module():
    """Load the runnable vendor script without triggering credentials or HTTP."""
    return import_module("scripts.vendor.typesafe.test_jev")


def test_smoke_plan_is_two_fixed_synthetic_requests_without_credentials():
    smoke = module()
    plan = smoke.build_plan()
    assert len(plan["requests"]) == 2
    assert plan["max_calls"] == 2
    assert plan["cost_ceiling_usd"] == "0.01"
    assert "authorization" not in json.dumps(plan).lower()
    assert plan["requests"][0]["model"] == "jev-latest"


def test_missing_grant_stops_before_loading_a_key(tmp_path):
    smoke = module()
    manifest = tmp_path / "delivery.json"
    manifest.write_text('{"external_calls": []}')
    decisions = tmp_path / "decisions.md"
    decisions.write_text("No paid authorization.")
    with pytest.raises(ValueError):
        smoke.verify_authorization(manifest, decisions, "D-999")


async def test_smoke_stops_at_first_error_without_retry_or_secret_output():
    smoke = module()
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(401, text="test-fixture-private-key")

    results = await smoke.run_batch(
        "test-fixture-private-key", transport=httpx.MockTransport(handler)
    )
    assert len(calls) == 1 and len(results) == 1
    assert results[0]["status"] == "http_401"
    assert "test-fixture-private-key" not in json.dumps(results)


async def test_smoke_uses_production_question_shape_and_records_only_safe_metadata():
    smoke = module()
    calls = []

    def handler(request):
        body = json.loads(request.content)
        calls.append(body)
        assert body == smoke.build_plan()["requests"][len(calls) - 1]
        return httpx.Response(
            200,
            json={
                "model": "jev-1.13.0",
                "usage": {"input_tokens": 200, "output_tokens": 10},
                "answers": {
                    "yield": {"type": "noul", "noul": 0.9},
                    "speech_state": {
                        "type": "choice",
                        "probabilities": {"complete": 0.8, "incomplete": 0.2},
                    },
                },
            },
        )

    results = await smoke.run_batch(
        "test-fixture-private-key", transport=httpx.MockTransport(handler)
    )
    assert len(calls) == 2 and all(row["status"] == "ok" for row in results)
    assert results[0]["input_tokens"] == 200
    assert "test-fixture-private-key" not in json.dumps(calls) + json.dumps(results)


def test_exact_grant_requires_confirmation_and_rejects_scope_changes(tmp_path):
    smoke = module()
    plan = smoke.build_plan()
    fields = ("batch_id", "request_sha256", "max_calls", "cost_ceiling_usd")
    grant = {key: plan[key] for key in fields}
    grant.update(authorization_decision_id="D-999", authorization_status="confirmed")
    manifest = tmp_path / "delivery.json"
    decisions = tmp_path / "decisions.md"
    manifest.write_text(json.dumps({"external_calls": [grant]}))
    decisions.write_text(
        "### D-999: Test fixture only\n- Status: Confirmed\n"
        "- Source thread/message: Synthetic unit test\n"
        "- Confirmation quote: Authorize only this mock batch.\n"
    )
    assert smoke.verify_authorization(manifest, decisions, "D-999") == grant
    grant["max_calls"] = 3
    manifest.write_text(json.dumps({"external_calls": [grant]}))
    with pytest.raises(ValueError):
        smoke.verify_authorization(manifest, decisions, "D-999")


def test_cli_without_authorization_never_loads_credentials(monkeypatch):
    smoke = module()
    touched = []
    monkeypatch.setattr(smoke, "local_key", lambda: touched.append(True))
    assert smoke.main([]) == 0
    assert smoke.main(["--execute", "--authorization-decision", "D-999"]) == 2
    assert not touched


async def test_failed_second_request_cannot_borrow_the_first_usage():
    smoke = module()
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) == 2:
            raise httpx.ConnectError("test-fixture-private-key", request=request)
        return httpx.Response(
            200,
            json={
                "model": "jev-1.13.0",
                "usage": {"input_tokens": 200, "output_tokens": 10},
                "answers": {
                    "yield": {"type": "noul", "noul": 0.9},
                    "speech_state": {
                        "type": "choice",
                        "probabilities": {"complete": 0.8, "incomplete": 0.2},
                    },
                },
            },
        )

    results = await smoke.run_batch(
        "test-fixture-private-key", transport=httpx.MockTransport(handler)
    )
    assert len(calls) == 2
    assert results[1]["status"] == "transport_error"
    assert "input_tokens" not in results[1] and "model" not in results[1]
    assert "test-fixture-private-key" not in json.dumps(results)
