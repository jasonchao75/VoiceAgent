"""Validate build-context inclusion with Docker itself, never Git ignore semantics."""

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(
    os.environ.get("VOICE_AGENT_DOCKER_CONTEXT_TEST") != "1",
    reason="Requires an explicitly enabled local Docker context probe; no real data is copied",
)


@pytest.fixture(scope="module")
def exported_context(tmp_path_factory):
    """Export a scratch image containing only inert sentinel paths through real BuildKit."""
    base = tmp_path_factory.mktemp("docker-context")
    context, output = base / "input", base / "output"
    context.mkdir()
    (context / ".dockerignore").write_text((ROOT / ".dockerignore").read_text())
    (context / "Dockerfile").write_text("FROM scratch\nCOPY . /context\n")
    for name in [
        "frontend/demo.html",
        "frontend/evaluation.html",
        "frontend/login.html",
        "scripts/deploy/verify_webrtc_production.py",
        "src/api.py",
        "frontend/.env",
        "frontend/node_modules/inert.txt",
        ".env",
        "openspec/changes/current/private-evidence.txt",
    ]:
        path = context / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("INERT SENTINEL ONLY\n")
    subprocess.run(
        ["docker", "build", "--output", f"type=local,dest={output}", str(context)],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    return output / "context"


@pytest.mark.parametrize(
    "required",
    [
        "frontend/demo.html",
        "frontend/evaluation.html",
        "frontend/login.html",
        "scripts/deploy/verify_webrtc_production.py",
        "src/api.py",
    ],
)
def test_declared_input_reaches_real_docker_context(exported_context, required):
    """Required sources must survive Docker's actual filtering rules."""
    assert (exported_context / required).is_file()


@pytest.mark.parametrize(
    "excluded",
    [
        "frontend/.env",
        "frontend/node_modules/inert.txt",
        ".env",
        "openspec/changes/current/private-evidence.txt",
    ],
)
def test_private_or_generated_input_stays_out(exported_context, excluded):
    """Do not copy secrets, dependencies or unrelated review evidence into build context."""
    assert not (exported_context / excluded).exists()
