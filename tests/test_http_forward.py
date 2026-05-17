"""Tests for HTTP forward proxy behaviour in ``handle_responses``.

The proxy relays mapped Chat Completions requests via the OpenAI SDK
and streams the transformed response back as SSE.
"""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import httpx
import openai
import pytest
from fastapi.testclient import TestClient
from openai.types.chat import ChatCompletionChunk

from primal_codex.config import PrimalCodexConfig, ProviderConfig, compute_model_map
from primal_codex.models import ModelConfig
from primal_codex.responses import ResponsesApiRequest
from primal_codex.run_serve import AppContext, app

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Generator

_VALID_BODY = ResponsesApiRequest(
    model="crof/glm-5",
    input=[{"role": "user", "content": [{"type": "input_text", "text": "Hi"}]}],
    tools=[],
    tool_choice="auto",
    parallel_tool_calls=True,
    instructions="",
    store=False,
    stream=True,
    include=[],
    reasoning=None,
    service_tier=None,
    prompt_cache_key=None,
    text=None,
    client_metadata=None,
).model_dump(mode="json")


def _make_config() -> PrimalCodexConfig:
    """Return a config with one provider (crof) exposing glm-5."""
    return PrimalCodexConfig(
        providers={
            "crof": ProviderConfig(
                base_url="https://crof.ai/v1",
                models={
                    "glm-5": ModelConfig(display_name="GLM-5"),
                },
            ),
        }
    )


def _setup_app_ctx(config: PrimalCodexConfig) -> None:
    """Set the module-level app context for testing."""
    app.state.ctx = AppContext(
        primal_config=config,
        model_map=compute_model_map(config),
    )


@pytest.fixture(autouse=True)
def _auto_ctx() -> Generator[None, None, None]:
    """Set a default app context before each test, clean up after."""
    _setup_app_ctx(_make_config())
    yield
    if hasattr(app.state, "ctx"):
        del app.state.ctx


@pytest.fixture
def client() -> TestClient:
    """Return a TestClient for the Primal Codex app."""
    return TestClient(app, raise_server_exceptions=False)


async def _mock_openai_chunks(
    chunks: list[ChatCompletionChunk] | None = None,
) -> AsyncIterator[ChatCompletionChunk]:
    """Yield mock ``ChatCompletionChunk`` objects."""
    if chunks is None:
        chunks = [
            ChatCompletionChunk(
                id="x",
                object="chat.completion.chunk",
                created=1,
                model="gpt-4",
                choices=[{"delta": {"role": "assistant"}, "index": 0}],
            ),
            ChatCompletionChunk(
                id="x",
                object="chat.completion.chunk",
                created=1,
                model="gpt-4",
                choices=[{"delta": {"content": "Hello"}, "index": 0}],
            ),
        ]
    for c in chunks:
        yield c


class TestUpstreamCall:
    """Verify that valid requests are forwarded to the upstream provider."""

    def test_makes_openai_chat_completions_call(self, client: TestClient) -> None:
        """Call ``AsyncOpenAI.chat.completions.create`` with mapped params."""
        mock_create = AsyncMock(return_value=_mock_openai_chunks())

        with patch(
            "primal_codex.responses.AsyncOpenAI",
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.chat.completions.create = mock_create
            mock_client_cls.return_value = mock_client

            response = client.post("/responses", json=_VALID_BODY)

        assert response.status_code == HTTPStatus.OK
        mock_create.assert_called_once()
        _, kwargs = mock_create.call_args
        assert kwargs["model"] == "glm-5"
        assert kwargs["stream"] is True
        assert kwargs["messages"] == [
            {"role": "user", "content": [{"type": "text", "text": "Hi"}]}
        ]
        assert set(kwargs) == {"model", "messages", "stream"}, (
            f"unexpected keys: {set(kwargs) - {'model', 'messages', 'stream'}}"
        )

    def test_transforms_and_relays_chunks(self, client: TestClient) -> None:
        """Transform OpenAI chunks to Responses API SSE events."""
        chunks = [
            ChatCompletionChunk(
                id="x",
                object="chat.completion.chunk",
                created=1,
                model="gpt-4",
                choices=[{"delta": {"content": "A"}, "index": 0}],
            ),
            ChatCompletionChunk(
                id="x",
                object="chat.completion.chunk",
                created=1,
                model="gpt-4",
                choices=[{"delta": {"content": "B"}, "index": 0}],
            ),
        ]
        mock_create = AsyncMock(return_value=_mock_openai_chunks(chunks))

        with patch(
            "primal_codex.responses.AsyncOpenAI",
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.chat.completions.create = mock_create
            mock_client_cls.return_value = mock_client

            response = client.post("/responses", json=_VALID_BODY)

        lines = response.content.decode().split("\n")
        assert lines[0] == "event: response.output_text.delta"
        assert '"delta":"A"' in lines[1]
        assert '"type":"response.output_text.delta"' in lines[1]
        assert lines[3] == "event: response.output_text.delta"
        assert '"delta":"B"' in lines[4]
        assert '"type":"response.output_text.delta"' in lines[4]
        assert lines[6] == "event: response.completed"
        assert '"type":"response.completed"' in lines[7]

    def test_sse_error_on_connection_error(self, client: TestClient) -> None:
        """Yield SSE error event when the upstream is unreachable."""
        dummy_request = httpx.Request("POST", "http://upstream")
        with patch(
            "primal_codex.responses.AsyncOpenAI",
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.chat.completions.create.side_effect = openai.APIError(
                "upstream refused", request=dummy_request, body=None
            )
            mock_client_cls.return_value = mock_client

            response = client.post("/responses", json=_VALID_BODY)

        assert response.status_code == HTTPStatus.OK
        assert "error" in response.text.lower()
        assert "connection" in response.text.lower()
