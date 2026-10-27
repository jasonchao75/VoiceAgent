"""A mixed browser fixture must not widen its vendor capability or chargeable text."""

import socket
from importlib import import_module

import pytest


def fixture():
    return import_module("tests.ui.td_tts_browser_app")


def test_dry_or_unapproved_mode_never_loads_key(monkeypatch):
    module = fixture()
    monkeypatch.setattr(module, "local_key", lambda: pytest.fail("Key accessed"))
    assert module.main([]) == 0
    assert module.main(["--execute", "--authorization-decision", "D-999"]) == 2
    plan = module.build_plan()
    assert plan["max_connections"] == 1 and plan["max_calls"] == 2
    assert plan["asr_jev_llm_calls"] == 0


def test_egress_requires_exact_task_capability_and_destination(monkeypatch):
    module = fixture()
    calls = []
    monkeypatch.setattr(socket.socket, "connect", lambda sock, target: calls.append(target))
    monkeypatch.setattr(socket.socket, "connect_ex", lambda sock, target: calls.append(target))
    monkeypatch.setattr(socket.socket, "sendto", lambda sock, data, target: calls.append(target))
    restore = module.install_egress_guard({"203.0.113.10"})
    with socket.socket() as sock:
        with pytest.raises(RuntimeError):
            sock.connect(("203.0.113.10", 443))
        token = module.VENDOR_CONNECT.set(True)
        try:
            sock.connect(("203.0.113.10", 443))
            with pytest.raises(RuntimeError):
                sock.connect(("203.0.113.11", 443))
            with pytest.raises(RuntimeError):
                sock.connect_ex(("203.0.113.10", 80))
        finally:
            module.VENDOR_CONNECT.reset(token)
        sock.connect(("127.0.0.1", 18996))
    restore()
    assert calls == [("203.0.113.10", 443), ("127.0.0.1", 18996)]


def test_vendor_capability_cannot_connect_udp(monkeypatch):
    module = fixture()
    monkeypatch.setattr(socket.socket, "connect", lambda *_: None)
    restore = module.install_egress_guard({"203.0.113.10"})
    token = module.VENDOR_CONNECT.set(True)
    try:
        with socket.socket(type=socket.SOCK_DGRAM) as sock:
            with pytest.raises(RuntimeError):
                sock.connect(("203.0.113.10", 443))
    finally:
        module.VENDOR_CONNECT.reset(token)
        restore()


@pytest.mark.parametrize("identity", [None, "", "wrong-id"])
def test_old_metadata_requires_matching_started_identity(identity):
    module = fixture()
    with pytest.raises(ValueError):
        module.require_old_identity(identity, ["old-id"])
    module.require_old_identity("old-id", ["old-id"])


@pytest.mark.asyncio
async def test_batch_stop_aborts_only_owned_connections():
    module = fixture()

    class Transport:
        aborted = False

        def abort(self):
            self.aborted = True

    class Connection:
        transport = Transport()

    owned = Connection()
    untouched = Connection()
    untouched.transport = Transport()
    await module.stop_owned_connections([owned])
    assert owned.transport.aborted
    assert not untouched.transport.aborted
