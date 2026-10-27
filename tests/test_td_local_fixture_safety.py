"""Local fixtures must reject UDP/TCP egress before any real socket operation."""

import socket

import pytest

from tests.ui.td_local_app import block_external_connections


def test_loopback_guard_rejects_udp_and_connect_ex_without_sending(monkeypatch):
    """Stub native operations first so the red test cannot send an external packet."""
    calls = []

    def connect(sock, address):
        calls.append(("connect", address))

    def connect_ex(sock, address):
        calls.append(("connect_ex", address))
        return 0

    def sendto(sock, data, *args):
        calls.append(("sendto", args[-1]))
        return len(data)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
    monkeypatch.setattr(socket.socket, "sendto", sendto)
    if hasattr(socket.socket, "sendmsg"):
        monkeypatch.setattr(socket.socket, "sendmsg", lambda *args: 1)
    block_external_connections()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        with pytest.raises(RuntimeError, match="External"):
            sock.sendto(b"not-a-real-packet", ("203.0.113.1", 3478))
        with pytest.raises(RuntimeError, match="External"):
            sock.connect_ex(("203.0.113.1", 443))
        if hasattr(sock, "sendmsg"):
            with pytest.raises(RuntimeError, match="External"):
                sock.sendmsg([b"x"], [], 0, ("203.0.113.1", 3478))
        assert sock.sendto(b"x", ("127.0.0.1", 1234)) == 1
        assert sock.connect_ex(("127.0.0.1", 1234)) == 0
    assert calls == [("sendto", ("127.0.0.1", 1234)), ("connect_ex", ("127.0.0.1", 1234))]
