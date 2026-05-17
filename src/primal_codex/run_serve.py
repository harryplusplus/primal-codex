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
async def responses(request: Request) -> JSONResponse | StreamingResponse:
    """Relay upstream responses as JSON or SSE.

    Accepts an OpenAI Responses API request body and relays it to
    the appropriate provider as a Chat Completions request.
    """
    return await handle_responses(request)


def run_serve() -> None:
    """Start the FastAPI server."""
    primal_config = load_config()
    app.state.ctx = AppContext(
        primal_config=primal_config,
        model_map=compute_model_map(primal_config),
    )
    uvicorn_config = uvicorn.Config(
        app,
        host=primal_config.server.host,
        port=primal_config.server.port,
    )
    server = uvicorn.Server(uvicorn_config)
    server.run()
