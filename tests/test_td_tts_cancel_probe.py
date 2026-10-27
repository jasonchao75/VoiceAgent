"""A real cancellation probe must remain inside its frozen text and connection budget."""

import asyncio
import json
from importlib import import_module

import pytest
from websockets.protocol import State


def probe():
    return import_module("scripts.evaluation.probe_td_tts_cancel")


def test_unapproved_probe_cannot_load_key(monkeypatch):
    module = probe()
    monkeypatch.setattr(module, "local_key", lambda: pytest.fail("Key accessed"))
    assert module.main([]) == 0
    assert module.main(["--execute", "--authorization-decision", "D-999"]) == 2
    plan = module.build_plan()
    assert plan["max_connections"] == 1 and plan["max_calls"] == 2
    assert plan["asr_jev_llm_calls"] == 0


class Socket:
    """Only the network socket is replaced; real SDK parsing and queues stay active."""

    def __init__(self, *, completed=False):
        self.state = State.OPEN
        self.response = None
        self.queue = asyncio.Queue()
        self.sent = []
        self.count = 0
        self.completed = completed

    def __aiter__(self):
        return self

    async def __anext__(self):
        item = await self.queue.get()
        if item is None:
            raise StopAsyncIteration
        return item

    async def send(self, encoded):
        message = json.loads(encoded)
        self.sent.append(message)
        kind = message["type"]
        if kind == "Configure":
            await self.queue.put(json.dumps({"type": "ConfigureSuccess"}))
        elif kind == "Speak":
            self.count += 1
            await self.queue.put(
                json.dumps({"type": "SpeechStarted", "speech_id": f"speech-{self.count}"})
            )
            await self.queue.put((b"\x01\x00" if self.count == 1 else b"\x02\x00") * 240)
            if self.count == 2 or self.completed:
                await self.queue.put(
                    json.dumps(
                        {
                            "type": "SpeechMetadata",
                            "speech_id": f"speech-{self.count}",
                            "billable_character_count": len(message["text"]),
                        }
                    )
                )
        elif kind == "Interrupt":
            await self.queue.put(b"\x09\x00" * 240)
            await self.queue.put(
                json.dumps({"type": "SpeechInterrupted", "metadata": {"speech_id": "speech-1"}})
            )

    async def close(self):
        self.state = State.CLOSED
        await self.queue.put(None)


async def test_actual_sdk_cancel_cycle_is_bounded_without_real_connection():
    socket = Socket()

    async def connect(*args, **kwargs):
        return socket

    result = await probe().run_case("inert-fixture-key", connector=connect)
    assert result["status"] == "ok"
    assert result["connections"] == 1
    assert result["speak_attempts"] == 2
    assert result["acknowledged_cancel"] is True
    assert result["new_output_samples"] > 0
    assert result["old_output_after_cancel_samples"] == 0


async def test_completed_turn_is_untriggered_without_second_paid_text():
    socket = Socket(completed=True)

    async def connect(*args, **kwargs):
        return socket

    result = await probe().run_case("inert-fixture-key", connector=connect)
    assert result["status"].startswith("not_triggered:")
    assert sum(m["type"] == "Speak" for m in socket.sent) == 1
