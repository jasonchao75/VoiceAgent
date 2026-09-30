"""Production WebRTC deployment preflight tests."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest


def _deploy_module() -> ModuleType:
    path = Path(__file__).parents[1] / "scripts/deploy/verify_webrtc_production.py"
    spec = importlib.util.spec_from_file_location("verify_webrtc_production", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_preflight_reports_only_safe_deployment_facts(tmp_path: Path) -> None:
    """Validate host networking and expose only count/range, never STUN URLs."""
    port_range = tmp_path / "ip_local_port_range"
    port_range.write_text("32768 60999\n", encoding="utf-8")
    result = _deploy_module().verify(
        environment={
            "VOICE_AGENT_STUN_URLS": "stun:one.example:3478,stuns:two.example:5349",
            "VOICE_AGENT_WEBRTC_HOST_NETWORK": "true",
        },
        port_range_path=port_range,
    )
    assert result == {
        "host_network": True,
        "stun_server_count": 2,
        "udp_ephemeral_port_range": [32768, 60999],
    }
    assert "example" not in str(result)


@pytest.mark.parametrize(
    ("environment", "message"),
    [
        ({"VOICE_AGENT_WEBRTC_HOST_NETWORK": "true"}, "STUN"),
        ({"VOICE_AGENT_STUN_URLS": "stun:one.example:3478"}, "host networking"),
        (
            {
                "VOICE_AGENT_STUN_URLS": "turn:relay.example:3478",
                "VOICE_AGENT_WEBRTC_HOST_NETWORK": "true",
            },
            "STUN",
        ),
    ],
)
def test_preflight_fails_closed(
    tmp_path: Path, environment: dict[str, str], message: str
) -> None:
    """Reject deployment when any first-release network invariant is missing."""
    port_range = tmp_path / "ip_local_port_range"
    port_range.write_text("32768 60999\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match=message):
        _deploy_module().verify(
            environment=environment,
            port_range_path=port_range,
        )


def test_deploy_rollback_supports_revisions_before_webrtc_override() -> None:
    """Keep rollback usable when the previous revision has only compose.yaml."""
    script = (
        Path(__file__).parents[1] / "scripts/deploy/platform_voiceagent.sh"
    ).read_text(encoding="utf-8")
    assert "if [[ -f compose.webrtc.yaml ]]" in script
    assert 'compose_files+=(-f compose.webrtc.yaml)' in script
    assert "Production WebRTC Compose override is missing" in script


def test_webrtc_lock_supports_runtime_python_311() -> None:
    """Keep aiortc's pyee dependency installable in the Python 3.11 image."""
    lock = (Path(__file__).parents[1] / "requirements.lock").read_text(encoding="utf-8")
    assert 'pyee==13.0.1 ; python_version < "3.12"' in lock
    assert 'pyee==14.0.0 ; python_version >= "3.12"' in lock
