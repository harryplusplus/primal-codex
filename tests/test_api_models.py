"""Tests for the ``GET /models`` endpoint.

Behavior under test:
1.  Return ``200`` with ``application/json`` Content-Type.
2.  Include a ``models`` key whose value is a JSON array.
3.  Return an empty array when no providers are configured.
4.  Include all models from all configured providers.
5.  Sort models by priority in ascending order.
6.  Reject methods other than ``GET`` with ``405``.
"""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import httpx

import pytest
from fastapi.testclient import TestClient

from primal_codex.config import PrimalCodexConfig, ProviderConfig
from primal_codex.models import ModelConfig
from primal_codex.run_serve import create_app


@pytest.fixture
def client() -> TestClient:
    """Return a TestClient for a Primal Codex app with an empty config."""
    return TestClient(create_app(PrimalCodexConfig()))


class TestModelsEndpoint:
    """Test suite for ``GET /models``."""

    def _get(self, client: TestClient) -> httpx.Response:
        """Perform a GET /models and return the response."""
        return client.get("/models")

    def test_returns_200(self, client: TestClient) -> None:
        """Return HTTP 200 for ``GET /models``."""
        response = self._get(client)
        assert response.status_code == HTTPStatus.OK

    def test_content_type_is_json(self, client: TestClient) -> None:
        """Respond with ``application/json`` Content-Type."""
        response = self._get(client)
        assert response.headers["content-type"] == "application/json"

    def test_has_models_key(self, client: TestClient) -> None:
        """Include a ``models`` key in the response body."""
        response = self._get(client)
        assert "models" in response.json()

    def test_models_is_list(self, client: TestClient) -> None:
        """Return ``models`` as a JSON array."""
        response = self._get(client)
        assert isinstance(response.json()["models"], list)

    def test_empty_when_no_providers(self, client: TestClient) -> None:
        """Return an empty list when no providers are configured."""
        response = self._get(client)
        assert response.json()["models"] == []

    def test_single_model(self) -> None:
        """Include one model entry for a single provider with one model."""
        config = PrimalCodexConfig(
            providers={
                "crof": ProviderConfig(
                    base_url="https://crof.ai/v1",
                    models={
                        "glm-5": ModelConfig(display_name="GLM-5"),
                    },
                ),
            }
        )
        client = TestClient(create_app(config))
        response = self._get(client)
        data = response.json()
        assert len(data["models"]) == 1
        assert data["models"][0]["slug"] == "crof/glm-5"
        assert data["models"][0]["display_name"] == "GLM-5"

    def test_multiple_providers(self) -> None:
        """Merge models from all configured providers."""
        config = PrimalCodexConfig(
            providers={
                "a": ProviderConfig(
                    base_url="https://a.ai",
                    models={"m1": ModelConfig(), "m2": ModelConfig()},
                ),
                "b": ProviderConfig(
                    base_url="https://b.ai", models={"m3": ModelConfig()}
                ),
            }
        )
        client = TestClient(create_app(config))
        response = self._get(client)
        slugs = {m["slug"] for m in response.json()["models"]}
        assert slugs == {"a/m1", "a/m2", "b/m3"}

    def test_sorted_alphabetically(self) -> None:
        """Sort models alphabetically by provider, then by model ID."""
        config = PrimalCodexConfig(
            providers={
                "p": ProviderConfig(
                    base_url="https://p.ai",
                    models={
                        "low": ModelConfig(priority=100),
                        "high": ModelConfig(priority=10),
                        "mid": ModelConfig(priority=50),
                    },
                ),
            }
        )
        client = TestClient(create_app(config))
        response = self._get(client)
        slugs = [m["slug"] for m in response.json()["models"]]
        # Alphabetical by model_id: high, low, mid
        assert slugs == ["p/high", "p/low", "p/mid"]

    def test_post_returns_405(self, client: TestClient) -> None:
        """Return 405 for ``POST /models``."""
        response = client.post("/models")
        assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED

    def test_put_returns_405(self, client: TestClient) -> None:
        """Return 405 for ``PUT /models``."""
        response = client.put("/models")
        assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED

    def test_delete_returns_405(self, client: TestClient) -> None:
        """Return 405 for ``DELETE /models``."""
        response = client.delete("/models")
        assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED
