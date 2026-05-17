"""Tests for the ``GET /healthz`` endpoint.

Behavior under test:
1.  Returns ``200`` with ``{"status": "ok"}``.
2.  Response Content-Type is ``application/json``.
3.  No unexpected extra keys in the response body.
4.  Other HTTP methods (POST, PUT, etc.) return ``405``.
"""

from __future__ import annotations

from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient

from primal_codex.run_serve import app


@pytest.fixture
def client() -> TestClient:
    """Return a TestClient for the Primal Codex app."""
    return TestClient(app)


class TestHealthz:
    """Test suite for ``GET /healthz``."""

    def test_returns_200(self, client: TestClient) -> None:
        """``GET /healthz`` returns HTTP 200."""
        response = client.get("/healthz")
        assert response.status_code == HTTPStatus.OK

    def test_returns_status_ok(self, client: TestClient) -> None:
        """The response body is ``{"status": "ok"}``."""
        response = client.get("/healthz")
        assert response.json() == {"status": "ok"}

    def test_content_type_is_json(self, client: TestClient) -> None:
        """The Content-Type header is ``application/json``."""
        response = client.get("/healthz")
        assert response.headers["content-type"] == "application/json"

    def test_no_extra_keys(self, client: TestClient) -> None:
        """The response body has exactly one key: ``status``."""
        response = client.get("/healthz")
        assert set(response.json().keys()) == {"status"}

    def test_post_returns_405(self, client: TestClient) -> None:
        """``POST /healthz`` returns HTTP 405 Method Not Allowed."""
        response = client.post("/healthz")
        assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED

    def test_put_returns_405(self, client: TestClient) -> None:
        """``PUT /healthz`` returns HTTP 405 Method Not Allowed."""
        response = client.put("/healthz")
        assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED

    def test_delete_returns_405(self, client: TestClient) -> None:
        """``DELETE /healthz`` returns HTTP 405 Method Not Allowed."""
        response = client.delete("/healthz")
        assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED
