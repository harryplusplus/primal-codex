"""Tests for the ``POST /responses`` relay endpoint.

The Primal Codex relays OpenAI Responses API requests to upstream Chat
Completions providers.  Tests are based on the actual ``ResponsesApiRequest``
schema used by the Codex client (see ``codex-api/src/common.rs``).

All fields match the ``ResponsesApiRequest`` Rust struct.
"""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Generator

import pytest
from fastapi.testclient import TestClient
from openai.types.chat import ChatCompletionChunk

from primal_codex.config import PrimalCodexConfig, ProviderConfig, compute_model_map
from primal_codex.models import ModelConfig
from primal_codex.responses import ResponsesApiRequest
from primal_codex.run_serve import AppContext, app

_VALID_MODEL = "crof/glm-5"


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
    """Set a default app context with mocked upstream before each test."""
    _setup_app_ctx(_make_config())

    async def _empty_stream() -> AsyncIterator[object]:
        """Yield a single [DONE]-like event then stop."""
        yield ChatCompletionChunk(
            id="x",
            object="chat.completion.chunk",
            created=1,
            model="gpt-4",
            choices=[{"delta": {"content": ""}, "index": 0, "finish_reason": "stop"}],
        )

    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=_empty_stream())
    with patch(
        "primal_codex.responses.AsyncOpenAI",
        return_value=mock_client,
    ):
        yield
    if hasattr(app.state, "ctx"):
        del app.state.ctx


@pytest.fixture
def client() -> TestClient:
    """Return a TestClient for the Primal Codex app."""
    return TestClient(app)


def _valid_body() -> dict[str, Any]:
    """Return a valid request body validated by ``ResponsesApiRequest``."""
    return ResponsesApiRequest(
        model=_VALID_MODEL,
        input=[{"role": "user", "content": [{"type": "input_text", "text": "Hello"}]}],
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


class TestValidRequest:
    """Verify that a well-formed request is accepted and relayed."""

    def test_returns_200(self, client: TestClient) -> None:
        """Return 200 for a valid streaming request."""
        response = client.post("/responses", json=_valid_body())
        assert response.status_code == HTTPStatus.OK

    def test_content_type_is_event_stream(self, client: TestClient) -> None:
        """Respond with ``text/event-stream`` content type."""
        response = client.post("/responses", json=_valid_body())
        assert response.headers.get("content-type") == "text/event-stream"

    def test_stream_false_returns_400(self, client: TestClient) -> None:
        """Return 400 when ``stream`` is ``false``."""
        body = _valid_body()
        body["stream"] = False
        response = client.post("/responses", json=body)
        assert response.status_code == HTTPStatus.BAD_REQUEST

    def test_no_stream_field_returns_400(self, client: TestClient) -> None:
        """Return 400 when ``stream`` is omitted."""
        body = _valid_body()
        del body["stream"]
        response = client.post("/responses", json=body)
        assert response.status_code == HTTPStatus.BAD_REQUEST


class TestInputValidation:
    """Verify that invalid or incomplete requests are rejected."""

    def test_missing_model_returns_400(self, client: TestClient) -> None:
        """Return 400 when ``model`` is missing."""
        body = _valid_body()
        del body["model"]
        response = client.post("/responses", json=body)
        assert response.status_code == HTTPStatus.BAD_REQUEST

    def test_missing_input_returns_400(self, client: TestClient) -> None:
        """Return 400 when ``input`` is missing."""
        body = _valid_body()
        del body["input"]
        response = client.post("/responses", json=body)
        assert response.status_code == HTTPStatus.BAD_REQUEST

    def test_unknown_model_returns_400(self, client: TestClient) -> None:
        """Return 400 when the model slug is not in the config."""
        body = _valid_body()
        body["model"] = "unknown/model"
        response = client.post("/responses", json=body)
        assert response.status_code == HTTPStatus.BAD_REQUEST

    def test_empty_body_returns_400(self, client: TestClient) -> None:
        """Return 400 when the request body is empty."""
        response = client.post(
            "/responses",
            content=b"",
            headers={"content-type": "application/json"},
        )
        assert response.status_code == HTTPStatus.BAD_REQUEST

    def test_invalid_json_returns_400(self, client: TestClient) -> None:
        """Return 400 when the request body is not valid JSON."""
        response = client.post(
            "/responses",
            content=b"not json",
            headers={"content-type": "application/json"},
        )
        assert response.status_code == HTTPStatus.BAD_REQUEST


class TestMethodNotAllowed:
    """Verify that only ``POST`` is accepted."""

    def test_get_returns_405(self, client: TestClient) -> None:
        """Return 405 for ``GET /responses``."""
        response = client.get("/responses")
        assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED

    def test_put_returns_405(self, client: TestClient) -> None:
        """Return 405 for ``PUT /responses``."""
        response = client.put("/responses", json=_valid_body())
        assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED

    def test_delete_returns_405(self, client: TestClient) -> None:
        """Return 405 for ``DELETE /responses``."""
        response = client.delete("/responses")
        assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED
