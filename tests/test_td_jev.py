"""JEV-02: no-network contract and bounded failure tests using httpx MockTransport."""

from importlib import import_module, util

import httpx
import pytest


def api():
    """Load the production Jev client after checking the integration exists."""
    assert util.find_spec("src.pipeline.jev") is not None, "Jev client absent"
    return import_module("src.pipeline.jev")


def payload():
    """Return an official System One response fixture with full distribution."""
    return {
        "answers": {
            "yield": {"type": "noul", "noul": 0.9},
            "state": {
                "type": "choice",
                "choice": "complete",
                "confidence": 0.6,
                "probabilities": {"complete": 0.8, "incomplete": 0.2},
            },
        }
    }


async def test_jev_sends_state_and_questions_without_local_waits():
    """The backend owns credentials; local wait mappings never enter provider questions."""
    jev = api()
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json=payload())

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        service = jev.JevClient(
            endpoint="https://api.typesafe.ai/v1/systemone",
            api_key="test-test-fixture-only-secret",
            client=client,
            max_calls=2,
        )
        result = await service.decide(
            model="jev-latest",
            state={"user": "hello"},
            questions={
                "yield": {"type": "noul"},
                "state": {"type": "choice", "criteria": {"complete": None, "incomplete": None}},
            },
            noul_id="yield",
            choice_id="state",
            timeout=1,
        )
    assert result.status == "ok" and result.noul == 0.9
    assert result.probabilities == {"complete": 0.8, "incomplete": 0.2}
    assert len(seen) == 1
    assert seen[0].headers["Authorization"] == "Bearer test-test-fixture-only-secret"
    assert "test-test-fixture-only-secret" not in repr(service)


@pytest.mark.parametrize("status", [401, 402, 429, 500])
async def test_http_failures_are_safe_without_retries(status):
    """Failures never become valid probabilities or leak response bodies."""
    jev = api()
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status, text="SECRET PROVIDER BODY")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        service = jev.JevClient(
            endpoint="https://api.typesafe.ai/v1/systemone",
            api_key="secret",
            client=client,
            max_calls=1,
        )
        result = await service.decide(
            model="jev-latest",
            state="hello",
            questions={},
            noul_id="yield",
            choice_id="state",
            timeout=1,
        )
        exhausted = await service.decide(
            model="jev-latest",
            state="hello",
            questions={},
            noul_id="yield",
            choice_id="state",
            timeout=1,
        )
    assert result.noul is None and result.probabilities is None
    assert result.status == f"http_{status}"
    assert "SECRET" not in repr(result)
    assert exhausted.status == "budget_exhausted" and len(calls) == 1


@pytest.mark.parametrize(
    "bad",
    [
        {},
        {"answers": {"yield": {"type": "noul", "noul": 0.8}}},
        {"answers": {"yield": {"type": "noul", "noul": float("inf")}}},
    ],
)
def test_malformed_answer_does_not_fabricate_probability(bad):
    """Missing answers and non-finite values are invalid evidence."""
    with pytest.raises(ValueError):
        api().parse_answer(
            bad, noul_id="yield", choice_id="state", option_ids={"complete", "incomplete"}
        )


async def test_uniform_100_attempt_budget_includes_failures_and_keeps_watchdog():
    """D-050 has no 101st HTTP attempt; exhaustion never bypasses the normal TD deadline."""
    from src.asr.td_config import CustomTDSettings
    from tests.test_td_config import td_settings
    from tests.test_td_runtime import coordinator, interim

    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(500)

    settings = CustomTDSettings.model_validate(td_settings()).jev
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        service = api().JevClient(
            endpoint=settings.endpoint,
            api_key="test-fixture-only",
            client=client,
            max_calls=settings.max_calls,
        )
        for _ in range(100):
            await service.decide(
                model=settings.model,
                state={},
                questions=settings.questions(),
                noul_id="yield",
                choice_id="speech_state",
                timeout=1,
            )
        result = await service.decide(
            model=settings.model,
            state={},
            questions=settings.questions(),
            noul_id="yield",
            choice_id="speech_state",
            timeout=1,
        )
        assert result.status == "budget_exhausted" and len(calls) == 100
        td = coordinator(decide=service.decide)
        frames = []

        async def push(frame, *args, **kwargs):
            frames.append(frame)

        td.push_frame = push
        await td.speech_started()
        await td.receive_transcript(interim("hello"))
        await td.speech_stopped(1000)
        if td._decision:
            await td._decision
        await td.advance(3499)
        assert td.responses.user_submission_count == 0
        await td.advance(3500)
        assert td.responses.user_submission_count == 1 and len(calls) == 100
