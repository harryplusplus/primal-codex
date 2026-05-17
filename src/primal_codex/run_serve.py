"""FastAPI server for Primal Codex."""

import asyncio
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

from primal_codex.config import PrimalCodexConfig, compute_model_infos, load_config
from primal_codex.models import ModelInfo, ModelsResponse


@dataclass
class AppContext:
    """Type-safe holder for application-wide state."""

    primal_config: PrimalCodexConfig
    model_infos: list[ModelInfo]
    relays: "ActiveRelays"


class ActiveRelays:
    """Track in-flight SSE relay streams for graceful shutdown."""

    def __init__(self) -> None:
        """Initialize an empty relay tracker."""
        self._tasks: set[asyncio.Task[Any]] = set()

    def wrap(self, gen: AsyncIterator[str]) -> AsyncIterator[str]:
        """Wrap a generator so its ASGI task lifecycle is tracked."""
        it = gen.__aiter__()

        async def _wrapped() -> AsyncIterator[str]:
            task = asyncio.current_task()
            if task is not None:
                self._tasks.add(task)
                task.add_done_callback(self._tasks.discard)
            async for item in it:
                yield item

        return _wrapped()

    async def wait_all(self) -> None:
        """Wait for all active relays with a 30-second timeout."""
        if not self._tasks:
            return
        try:
            async with asyncio.timeout(30.0):
                await asyncio.gather(*list(self._tasks), return_exceptions=True)
        except TimeoutError:
            pass


def _lookup_model(infos: list[ModelInfo], slug: str) -> ModelInfo | None:
    """Look up a model by its qualified slug from a model list."""
    for mi in infos:
        if mi.slug == slug:
            return mi
    return None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Load config once on startup; drain relays on shutdown."""
    primal_config = load_config()
    app.state.ctx = AppContext(
        primal_config=primal_config,
        model_infos=compute_model_infos(primal_config),
        relays=ActiveRelays(),
    )
    yield
    await app.state.ctx.relays.wait_all()


app = FastAPI(lifespan=lifespan)


@app.get("/healthz")
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
)
def models(request: Request) -> ModelsResponse:
    """List all models — reads from pre-computed model info."""
    return ModelsResponse(models=request.app.state.ctx.model_infos)


@app.post("/responses", response_model=None)
async def responses(
    request: Request,
) -> JSONResponse | StreamingResponse:
    """Relay upstream responses as JSON or SSE."""
    body = await request.json()
    stream = body.get("stream", False)

    # NOTE: placeholder; replace with actual upstream relay
    #   https://github.com/primal-codex/primal-codex/issues/1
    _ = body  # use body.get("model") for model lookup
    if stream:
        ctx: AppContext = request.app.state.ctx
        relays: ActiveRelays = ctx.relays

        async def _relay_stream() -> AsyncIterator[str]:
            """Relay upstream streaming chunks as SSE."""
            yield (
                "data: {"
                '"id":"resp_xxx",'
                '"object":"response",'
                '"status":"completed",'
                '"output":[{"type":"message","role":"assistant","content":[{"type":"output_text","text":"Hello","annotations":[]}]}]'
                "}\n\n"
            )

        return StreamingResponse(
            relays.wrap(_relay_stream()),
            media_type="text/event-stream",
        )

    return JSONResponse(
        {
            "id": "resp_xxx",
            "object": "response",
            "status": "completed",
            "output": [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [
                        {"type": "output_text", "text": "Hello", "annotations": []}
                    ],
                }
            ],
        }
    )


def run_serve() -> None:
    """Start the FastAPI server."""
    primal = PrimalCodexConfig()
    uvicorn_config = uvicorn.Config(
        app,
        host=primal.server.host,
        port=primal.server.port,
    )
    server = uvicorn.Server(uvicorn_config)
    server.run()
