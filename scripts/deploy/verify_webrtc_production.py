#!/usr/bin/env python3
"""Fail closed when production WebRTC deployment prerequisites are missing."""

from __future__ import annotations

import json
import os
from pathlib import Path


def verify(
    *,
    environment: dict[str, str] | None = None,
    port_range_path: Path = Path("/proc/sys/net/ipv4/ip_local_port_range"),
) -> dict[str, object]:
    """Validate safe non-secret production WebRTC deployment signals.

    Args:
        environment: Environment mapping, defaulting to the current process.
        port_range_path: Linux ephemeral UDP range source.

    Returns:
        Safe deployment facts suitable for CI/CD logs.

    Raises:
        RuntimeError: If STUN, host networking, or the UDP range is invalid.
    """
    values = os.environ if environment is None else environment
    urls = [
        item.strip()
        for item in values.get("VOICE_AGENT_STUN_URLS", "").split(",")
        if item.strip()
    ]
    if not urls or any(not url.startswith(("stun:", "stuns:")) for url in urls):
        raise RuntimeError("production WebRTC requires one or more STUN URLs")
    if values.get("VOICE_AGENT_WEBRTC_HOST_NETWORK", "").lower() != "true":
        raise RuntimeError("production WebRTC requires Linux host networking")
    try:
        lower_text, upper_text = port_range_path.read_text(encoding="utf-8").split()
        lower, upper = int(lower_text), int(upper_text)
    except (OSError, ValueError) as exc:
        raise RuntimeError("Linux ephemeral UDP range could not be read") from exc
    if lower < 1024 or upper <= lower or upper > 65535:
        raise RuntimeError("Linux ephemeral UDP range is invalid")
    return {
        "host_network": True,
        "stun_server_count": len(urls),
        "udp_ephemeral_port_range": [lower, upper],
    }


def main() -> None:
    """Print non-sensitive deployment facts after successful validation."""
    print(json.dumps(verify(), sort_keys=True))


if __name__ == "__main__":
    main()
