"""Tests for the ``POST /responses`` endpoint (placeholder phase).

Behavior under test:
1.  Return ``200`` for ``POST /responses`` with a valid JSON body.
2.  Return ``application/json`` for a non-streaming request.
3.  Return ``text/event-stream`` for a streaming request (``"stream": true``).
4.  Include the expected static placeholder fields in the response.
5.  Return ``400`` when the request body is empty or invalid JSON.
6.  Reject methods other than ``POST`` with ``405``.
"""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from primal_codex.config import PrimalCodexConfig, compute_model_infos
from primal_codex.run_serve import ActiveRelays, AppContext, app

_DEFAULT_BODY: dict[str, str] = {"input": "Hello"}


def _setup_app_ctx(config: PrimalCodexConfig) -> None:
    """Set the module-level app context for testing."""
    app.state.ctx = AppContext(
        primal_config=config,
        model_infos=compute_model_infos(config),
        relays=ActiveRelays(),
    )


@pytest.fixture(autouse=True)
def _auto_ctx() -> Generator[None, None, None]:
    """Set a default app context before each test, clean up after."""
    _setup_app_ctx(PrimalCodexConfig())
    yield
    if hasattr(app.state, "ctx"):
        del app.state.ctx


@pytest.fixture
def client() -> TestClient:
    """Return a TestClient for the Primal Codex app."""
    return TestClient(app)


class TestResponsesPlaceholder:
    """Test suite for ``POST /responses`` (placeholder)."""

    def test_returns_200(self, client: TestClient) -> None:
        """Return HTTP 200 for a valid POST request."""
        response = client.post("/responses", json=_DEFAULT_BODY)
        assert response.status_code == HTTPStatus.OK

    def test_content_type_json_for_non_streaming(self, client: TestClient) -> None:
        """Return ``application/json`` for a non-streaming request."""
        response = client.post("/responses", json=_DEFAULT_BODY)
        assert response.headers["content-type"] == "application/json"

    def test_content_type_sse_for_streaming(self, client: TestClient) -> None:
        """Start ``Content-Type`` with ``text/event-stream`` for streaming."""
        response = client.post("/responses", json={"stream": True})
        assert response.headers["content-type"].startswith("text/event-stream")

    def test_non_streaming_has_id(self, client: TestClient) -> None:
        """Include an ``id`` field in the JSON response body."""
        response = client.post("/responses", json=_DEFAULT_BODY)
        data = response.json()
        assert data["id"] == "resp_xxx"

    def test_non_streaming_has_object(self, client: TestClient) -> None:
        """Include an ``object`` field set to ``response``."""
        response = client.post("/responses", json=_DEFAULT_BODY)
        data = response.json()
        assert data["object"] == "response"

    def test_non_streaming_has_status(self, client: TestClient) -> None:
        """Include a ``status`` field set to ``completed``."""
        response = client.post("/responses", json=_DEFAULT_BODY)
        data = response.json()
        assert data["status"] == "completed"

    def test_non_streaming_has_output(self, client: TestClient) -> None:
        """Include an ``output`` array with a message containing ``Hello``."""
        response = client.post("/responses", json=_DEFAULT_BODY)
        data = response.json()
        assert len(data["output"]) == 1
        assert data["output"][0]["type"] == "message"
        assert data["output"][0]["role"] == "assistant"

        content = data["output"][0]["content"]
        assert len(content) == 1
        assert content[0]["type"] == "output_text"
        assert content[0]["text"] == "Hello"

    def test_streaming_content_includes_sse_event(self, client: TestClient) -> None:
        """Return SSE-formatted content for a streaming request."""
        response = client.post("/responses", json={"stream": True})
        text = response.text
        assert text.startswith("data: ")
        assert text.endswith("\n\n")
        assert '"id":"resp_xxx"' in text
        assert '"object":"response"' in text
        assert '"status":"completed"' in text
        assert '"text":"Hello"' in text

    @pytest.mark.xfail(
        reason=(
            "Placeholder does not catch JSONDecodeError — "
            "request.json() raises and remains unhandled, "
        ),
        strict=True,
    )
    def test_empty_body_returns_400(self, client: TestClient) -> None:
        """Return 400 when the request body is empty."""
        response = client.post(
            "/responses",
            content=b"",
            headers={"content-type": "application/json"},
        )
        assert response.status_code == HTTPStatus.BAD_REQUEST

    @pytest.mark.xfail(
        reason=(
            "Placeholder does not catch JSONDecodeError — "
            "request.json() raises and remains unhandled."
        ),
        strict=True,
    )
    def test_invalid_json_returns_400(self, client: TestClient) -> None:
        """Return 400 when the request body is not valid JSON."""
        response = client.post(
            "/responses",
            content=b"not json",
            headers={"content-type": "application/json"},
        )
        assert response.status_code == HTTPStatus.BAD_REQUEST

    def test_get_returns_405(self, client: TestClient) -> None:
        """Return 405 for ``GET /responses``."""
        response = client.get("/responses")
        assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED

    def test_put_returns_405(self, client: TestClient) -> None:
        """Return 405 for ``PUT /responses``."""
        response = client.put("/responses", json=_DEFAULT_BODY)
        assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED

    def test_delete_returns_405(self, client: TestClient) -> None:
        """Return 405 for ``DELETE /responses``."""
        response = client.delete("/responses")
        assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED
