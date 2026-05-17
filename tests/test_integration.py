"""Integration tests for Primal Codex via the codex CLI binary.

Exercises the codex CLI end-to-end through the Primal Codex proxy.
Requires the ``CROF_API_KEY`` environment variable.
"""

from __future__ import annotations

import json
import os
import shutil
import struct
import subprocess
import time
import zlib
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator

pytestmark = pytest.mark.skipif(
    "CROF_API_KEY" not in os.environ,
    reason="CROF_API_KEY environment variable is required",
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

_UV_BIN = os.environ.get("UV", shutil.which("uv") or "uv")
_CODEX_BIN = shutil.which("codex") or "codex"

SERVER_PORT = 8026
SERVER_URL = f"http://127.0.0.1:{SERVER_PORT}"

PRIMAL_CONFIG = """\
[server]
host = "127.0.0.1"
port = {port}

[providers.crof]
base_url = "https://crof.ai/v1"
env_key = "CROF_API_KEY"

[providers.crof.models."glm-5.1-precision"]
display_name = "Crof GLM-5.1 Precision"
input_modalities = ["text"]

[providers.crof.models."kimi-k2.6-precision"]
display_name = "Crof Kimi K2.6 Precision"
input_modalities = ["text", "image"]
"""

CODEX_CONFIG = """\
model_provider = "primal-codex"

[model_providers.primal-codex]
name = "primal-codex"
base_url = "{server_url}"
supports_websockets = false
"""


def _make_png_pixel(width: int, height: int, r: int, g: int, b: int) -> bytes:
    """Build a minimal valid PNG filled with a solid color."""
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    ihdr_crc = struct.pack(">I", zlib.crc32(b"IHDR" + ihdr_data) & 0xFFFFFFFF)
    ihdr = struct.pack(">I", 13) + b"IHDR" + ihdr_data + ihdr_crc
    raw = b""
    for _y in range(height):
        raw += b"\x00"
        raw += bytes([r, g, b]) * width
    compressed = zlib.compress(raw)
    idat_crc = struct.pack(">I", zlib.crc32(b"IDAT" + compressed) & 0xFFFFFFFF)
    idat = struct.pack(">I", len(compressed)) + b"IDAT" + compressed + idat_crc
    iend_crc = struct.pack(">I", zlib.crc32(b"IEND") & 0xFFFFFFFF)
    iend = struct.pack(">I", 0) + b"IEND" + iend_crc
    return sig + ihdr + idat + iend


_RED_PNG = _make_png_pixel(4, 4, 255, 0, 0)


def _json_events(stdout: str) -> list[dict[str, object]]:
    """Parse JSONL lines from codex stdout."""
    events: list[dict[str, object]] = []
    for line in stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            events.append(json.loads(stripped))
        except json.JSONDecodeError:
            continue
    return events


def _agent_response(events: list[dict[str, object]]) -> str:
    """Extract the assistant's text from codex thread events."""
    parts: list[str] = []
    for ev in events:
        t = ev.get("type", "")
        if t == "item.completed":
            item = ev.get("item", {})
            if isinstance(item, dict) and item.get("role") == "assistant":
                content = item.get("content", [])
                if isinstance(content, list):
                    for c in content:
                        if isinstance(c, dict) and c.get("type") == "output_text":
                            text = c.get("text", "")
                            if isinstance(text, str) and text:
                                parts.append(text)
                elif isinstance(content, str):
                    parts.append(content)
    return "\n".join(parts)


def _thread_id(events: list[dict[str, object]]) -> str | None:
    """Extract the thread ID from codex events."""
    for ev in events:
        t = ev.get("type", "")
        if t == "turn.started":
            tid = ev.get("thread_id") or ev.get("turn_id")
            if isinstance(tid, str):
                return tid
    for ev in events:
        t = ev.get("type", "")
        if t == "thread.started":
            tid = ev.get("thread_id")
            if isinstance(tid, str):
                return tid
    return None


def _run_codex(
    prompt: str,
    codex_home: str,
    model: str = "crof/glm-5.1-precision",
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run ``codex exec --json`` and return the result."""
    cmd = [
        _CODEX_BIN,
        "exec",
        "--json",
        prompt,
        "--model",
        model,
    ]
    full_env = os.environ.copy()
    full_env["CODEX_HOME"] = codex_home
    full_env["CLICOLOR"] = "0"
    full_env["NO_COLOR"] = "1"
    if env:
        full_env.update(env)
    return subprocess.run(  # noqa: S603
        cmd,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        stdin=subprocess.DEVNULL,
        env=full_env,
        cwd=str(PROJECT_ROOT),
    )


@pytest.fixture(scope="session")
def server(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    """Start the primal-codex server and return its URL."""
    primal_home = tmp_path_factory.mktemp("primal")
    (primal_home / "config.toml").write_text(PRIMAL_CONFIG.format(port=SERVER_PORT))

    env = os.environ.copy()
    env["PRIMAL_CODEX_HOME"] = str(primal_home)

    proc = subprocess.Popen(  # noqa: S603
        [_UV_BIN, "run", "primal-codex", "serve"],
        env=env,
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        for _attempt in range(30):
            try:
                r = httpx.get(f"{SERVER_URL}/healthz", timeout=1)
                if r.status_code == 200:
                    break
            except (httpx.ConnectError, httpx.ReadTimeout):
                pass
            time.sleep(0.5)
        else:
            pytest.fail("primal-codex server did not start within 15s")
        yield SERVER_URL
    finally:
        proc.terminate()
        proc.wait(timeout=10)


@pytest.fixture
def codex_env(server: str, tmp_path: Path) -> str:
    """Create a codex home directory and return its path."""
    del server
    codex_home = str(tmp_path / "codex")
    codex_dir = Path(codex_home)
    codex_dir.mkdir(parents=True, exist_ok=True)
    (codex_dir / "config.toml").write_text(CODEX_CONFIG.format(server_url=SERVER_URL))
    return codex_home


class TestTextInput:
    """Basic text prompts via the codex CLI."""

    def test_simple_greeting(self, codex_env: str) -> None:
        """Codex returns a non-empty response for a greeting."""
        result = _run_codex("Reply only with the word pineapple.", codex_env)
        response = _agent_response(_json_events(result.stdout))
        assert response, f"No agent response. stderr: {result.stderr[:300]}"
        assert "pineapple" in response.lower(), f"Unexpected: {response}"

    def test_instructions_followed(self, codex_env: str) -> None:
        """Codex follows system-level instructions."""
        result = _run_codex(
            "What is the secret word? If you don't know, reply UNKNOWN.",
            codex_env,
        )
        response = _agent_response(_json_events(result.stdout))
        assert response, f"No response: {result.stderr[:300]}"
        assert "UNKNOWN" in response.upper(), f"Unexpected: {response}"


class TestSessionResume:
    """Multi-turn session persistence."""

    def test_resume_remembers_context(self, codex_env: str) -> None:
        """Codex remembers context across two turns."""
        result1 = _run_codex(
            'Remember the secret animal is "okapi". Reply OK.', codex_env
        )
        events1 = _json_events(result1.stdout)
        response1 = _agent_response(events1)
        assert response1, "Turn 1 empty"

        tid = _thread_id(events1)
        assert tid, "No thread ID found"

        # Turn 2: resume the same session
        cmd = [
            _CODEX_BIN,
            "exec",
            "resume",
            tid,
            "--json",
            "What is the secret animal? Reply with the word only.",
            "--model",
            "crof/glm-5.1-precision",
        ]
        full_env = os.environ.copy()
        full_env["CODEX_HOME"] = codex_env
        full_env["CLICOLOR"] = "0"
        full_env["NO_COLOR"] = "1"

        result2 = subprocess.run(  # noqa: S603
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
            stdin=subprocess.DEVNULL,
            env=full_env,
            cwd=str(PROJECT_ROOT),
        )
        response2 = _agent_response(_json_events(result2.stdout))
        assert response2, f"Turn 2 empty. stderr: {result2.stderr[:300]}"
        assert "okapi" in response2.lower(), f"Did not remember: {response2}"

    def test_resume_with_new_model(self, codex_env: str) -> None:
        """Resuming with a different model still works."""
        result1 = _run_codex(
            'Remember "persist_test" means "verified". Reply OK.', codex_env
        )
        events1 = _json_events(result1.stdout)
        tid = _thread_id(events1)
        assert tid, "No thread ID"

        cmd = [
            _CODEX_BIN,
            "exec",
            "resume",
            tid,
            "--json",
            'What does "persist_test" mean? Reply with the word only.',
            "--model",
            "crof/glm-5.1-precision",
        ]
        full_env = os.environ.copy()
        full_env["CODEX_HOME"] = codex_env
        full_env["CLICOLOR"] = "0"
        full_env["NO_COLOR"] = "1"

        result2 = subprocess.run(  # noqa: S603
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
            stdin=subprocess.DEVNULL,
            env=full_env,
            cwd=str(PROJECT_ROOT),
        )
        response2 = _agent_response(_json_events(result2.stdout))
        assert response2, f"No response: {result2.stderr[:300]}"
        assert "persist_test" in response2.lower(), f"Did not remember: {response2}"
