"""FastAPI server for Primal Codex."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.metadata import version

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

from primal_codex.config import PrimalCodexConfig, compute_model_map, load_config
from primal_codex.models import ModelInfo, ModelsResponse
from primal_codex.responses import handle_responses


@dataclass
class AppContext:
    """Type-safe holder for application-wide state."""

    primal_config: PrimalCodexConfig
    model_map: dict[str, ModelInfo]


def _register_routes(app: FastAPI) -> None:
    """Register route handlers on the given FastAPI application."""

    @app.get(
        "/healthz",
        summary="Health Check",
        description="Returns a simple status to confirm the server is running.",
        tags=["system"],
    )
    async def healthz() -> JSONResponse:
        """Health check endpoint."""
        return JSONResponse({"status": "ok"})

    @app.get(
        "/models",
        summary="List Models",
        description=(
            "Return metadata for all models discovered from configured providers."
        ),
        tags=["models"],
        operation_id="list_models",
    )
    def models(request: Request) -> ModelsResponse:
        """List all models — reads from pre-computed model info."""
        return ModelsResponse(models=list(request.app.state.ctx.model_map.values()))

    @app.post("/responses", response_model=None)
    async def responses(
        request: Request,
    ) -> JSONResponse | StreamingResponse:
        """Relay upstream responses as JSON or SSE.

        Accepts an OpenAI Responses API request body and relays it to
        the appropriate provider as a Chat Completions request.
        """
        return await handle_responses(request)


def build_app(raw_config: dict[str, object] | None = None) -> FastAPI:
    """Build and return a configured FastAPI application."""
    if raw_config is not None:
        primal_config = PrimalCodexConfig.model_validate(raw_config)
    else:
        primal_config = load_config()

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
    _register_routes(app)
    return app


app = build_app()


def run_serve() -> None:
    """Start the FastAPI server."""
    app.state.ctx = AppContext(
        primal_config=load_config(),
        model_map=compute_model_map(load_config()),  # type: ignore[arg-type]
    )
    uvicorn_config = uvicorn.Config(
        app,
        host=app.state.ctx.primal_config.server.host,
        port=app.state.ctx.primal_config.server.port,
    )
    server = uvicorn.Server(uvicorn_config)
    server.run()
