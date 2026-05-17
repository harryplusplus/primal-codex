"""Tests for the ``GET /healthz`` endpoint.

Behavior under test:
1.  Return ``200`` with ``{"status": "ok"}``.
2.  Respond with Content-Type ``application/json``.
3.  Omit extra keys beyond ``status``.
4.  Reject methods other than ``GET`` with ``405``.
"""

from __future__ import annotations

from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient

from primal_codex.config import PrimalCodexConfig
from primal_codex.run_serve import create_app


@pytest.fixture
def client() -> TestClient:
    """Return a TestClient for a fresh Primal Codex app."""
    return TestClient(create_app(PrimalCodexConfig()))


class TestHealthz:
    """Test suite for ``GET /healthz``."""

    def test_returns_200(self, client: TestClient) -> None:
        """Return HTTP 200 for ``GET /healthz``."""
        response = client.get("/healthz")
        assert response.status_code == HTTPStatus.OK

    def test_returns_status_ok(self, client: TestClient) -> None:
        """Return ``{"status": "ok"}`` in the response body."""
        response = client.get("/healthz")
        assert response.json() == {"status": "ok"}

    def test_content_type_is_json(self, client: TestClient) -> None:
        """Respond with ``application/json`` Content-Type."""
        response = client.get("/healthz")
        assert response.headers["content-type"] == "application/json"

    def test_no_extra_keys(self, client: TestClient) -> None:
        """Include exactly one key in the response: ``status``."""
        response = client.get("/healthz")
        assert set(response.json().keys()) == {"status"}

    def test_post_returns_405(self, client: TestClient) -> None:
        """Return 405 for ``POST /healthz``."""
        response = client.post("/healthz")
        assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED

    def test_put_returns_405(self, client: TestClient) -> None:
        """Return 405 for ``PUT /healthz``."""
        response = client.put("/healthz")
        assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED

    def test_delete_returns_405(self, client: TestClient) -> None:
        """Return 405 for ``DELETE /healthz``."""
        response = client.delete("/healthz")
        assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED
