"""Tests for the HTTP forward proxy (``_relay_stream``)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import openai
import pytest
from fastapi.testclient import TestClient
from openai import AsyncOpenAI

from primal_codex.run_serve import build_app

_VALID_BODY: dict[str, object] = {
    "model": "test-provider/test-model",
    "input": [{"role": "user", "content": "Hello"}],
    "stream": True,
}


def _mock_chunk(content: str | None, finish: str | None = None) -> MagicMock:
    """Build a mock ``ChatCompletionChunk``."""
    delta = MagicMock()
    delta.content = content
    delta.role = "assistant"
    delta.tool_calls = None
    choice = MagicMock()
    choice.index = 0
    choice.finish_reason = finish
    choice.logprobs = None
    choice.delta = delta
    choices = [choice]
    chunk = MagicMock()
    chunk.id = "chunk_1"
    chunk.object = "chat.completion.chunk"
    chunk.created = 1234567890
    chunk.model = "test-model"
    chunk.choices = choices
    chunk.usage = None
    return chunk


def _make_config() -> dict[str, Any]:
    """Build a minimal config dict for testing."""
    return {
        "server": {"host": "127.0.0.1", "port": 8099},
        "providers": {
            "test-provider": {
                "base_url": "https://upstream.test",
                "env_key": "TEST_API_KEY",
                "models": {
                    "test-model": {
                        "display_name": "Test Model",
                    },
                },
            },
        },
    }


class _MockAsyncStream:
    """An async-iterable stream that yields predefined chunks."""

    def __init__(self, chunks: list[MagicMock]) -> None:
        self._chunks = list(chunks)
        self._index = 0

    def __aiter__(self) -> _MockAsyncStream:
        return self

    async def __anext__(self) -> MagicMock:
        if self._index >= len(self._chunks):
            raise StopAsyncIteration
        val = self._chunks[self._index]
        self._index += 1
        return val


def _make_mock_async_openai(
    chunks: list[MagicMock] | None = None,
) -> MagicMock:
    """Build a mock ``AsyncOpenAI`` with a controlled stream response."""
    if chunks is None:
        chunks = [_mock_chunk("A"), _mock_chunk("B")]

    async def mock_create(**_kwargs: object) -> _MockAsyncStream:
        return _MockAsyncStream(chunks)

    mock_client = MagicMock(spec=AsyncOpenAI)
    mock_client.chat.completions.create = mock_create
    return mock_client


def _patch_async_openai(
    monkeypatch: pytest.MonkeyPatch, mock_client: MagicMock
) -> None:
    """Patch ``AsyncOpenAI`` so ``_relay_stream`` uses the given mock."""
    mock_cm = MagicMock()
    mock_cm.__aenter__.return_value = mock_client
    monkeypatch.setattr(
        "primal_codex.responses.AsyncOpenAI",
        lambda *_args, **_kwargs: mock_cm,
    )


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """FastAPI ``TestClient`` with mocked async client."""
    raw_config = _make_config()
    app = build_app(raw_config)
    monkeypatch.setenv("TEST_API_KEY", "sk-test123")

    mock_client = _make_mock_async_openai()
    _patch_async_openai(monkeypatch, mock_client)

    return TestClient(app)


class TestUpstreamCall:
    """Verify the relay stream emits correct SSE events."""

    def test_transforms_and_relays_chunks(self, client: TestClient) -> None:
        """Content chunks are relayed as ``response.output_text.delta`` events."""
        response = client.post("/responses", json=_VALID_BODY)
        assert response.status_code == 200

        lines = response.content.decode().split("\n")
        # response.created (index 0-1)
        assert lines[0] == "event: response.created"
        assert '"type":"response.created"' in lines[1]
        assert '"response"' in lines[1]

        # response.output_item.added (index 3-4)
        assert lines[3] == "event: response.output_item.added"
        assert '"type":"response.output_item.added"' in lines[4]
        assert '"type":"message"' in lines[4]

        # output_text.delta: A (index 6-7)
        assert lines[6] == "event: response.output_text.delta"
        assert '"delta":"A"' in lines[7]
        assert '"type":"response.output_text.delta"' in lines[7]

        # output_text.delta: B (index 9-10)
        assert lines[9] == "event: response.output_text.delta"
        assert '"delta":"B"' in lines[10]
        assert '"type":"response.output_text.delta"' in lines[10]

        # response.completed (index 12-13)
        assert lines[12] == "event: response.completed"
        assert '"type":"response.completed"' in lines[13]
        assert '"status":"completed"' in lines[13]

    def test_sse_error_on_connection_error(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Yield ``response.failed`` event when the upstream is unreachable."""
        # Patch with a client whose create method raises
        mock_client = MagicMock(spec=AsyncOpenAI)

        async def failing_create(**_kwargs: object) -> None:
            raise openai.APIError(
                message="Connection refused",
                request=openai.BaseModel(),
                body=None,
            )

        mock_client.chat.completions.create = failing_create
        _patch_async_openai(monkeypatch, mock_client)

        response = client.post("/responses", json=_VALID_BODY)
        assert response.status_code == 200
        body = response.content.decode()
        assert '"type":"response.failed"' in body
        assert '"code":"upstream_error"' in body
        assert '"status":"failed"' in body
