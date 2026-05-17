"""FastAPI server for Primal Codex."""

from __future__ import annotations

from importlib.metadata import version

import uvicorn
from fastapi import FastAPI

from primal_codex.app_context import AppContext
from primal_codex.config import PrimalCodexConfig, compute_model_map, load_config
from primal_codex.routes_healthz import router as healthz_router
from primal_codex.routes_models import router as models_router
from primal_codex.routes_responses import router as responses_router


def create_app(primal_config: PrimalCodexConfig) -> FastAPI:
    """Build and return a configured FastAPI application.

    This is a pure factory — it does not load any configuration on its own.
    Callers are responsible for providing a fully resolved
    :class:`PrimalCodexConfig`.

    Args:
        primal_config: Fully resolved application configuration.

    Returns:
        A fully configured FastAPI application ready to serve.

    """
    app = FastAPI(
        title="Primal Codex",
        summary="OpenAI Responses API to Chat Completions reverse proxy",
        description=(
            "Maps Codex Responses API requests to OpenAI-compatible Chat"
            " Completions endpoints for open-source model providers."
        ),
        version=version("primal-codex"),
        docs_url=None,
        redoc_url=None,
    )

    app.state.ctx = AppContext(
        primal_config=primal_config,
        model_map=compute_model_map(primal_config),
    )
    app.include_router(healthz_router)
    app.include_router(models_router)
    app.include_router(responses_router)
    return app


def run_serve() -> None:
    """Start the FastAPI server."""
    primal_config = load_config()
    app = create_app(primal_config)
    uvicorn_config = uvicorn.Config(
        app,
        host=primal_config.server.host,
        port=primal_config.server.port,
    )
    server = uvicorn.Server(uvicorn_config)
    server.run()
