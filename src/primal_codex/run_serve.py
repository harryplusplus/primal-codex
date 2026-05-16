"""FastAPI server for Primal Codex with HTTP and SSE support."""

import asyncio
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

from primal_codex.config import load_config


class ActiveRelays:
    """Track in-flight SSE relay streams for graceful shutdown.

    Wraps an async generator so that the ASGI streaming Task is captured
    via ``asyncio.current_task()`` and automatically removed from the
    pending set when the task finishes (``add_done_callback``).
    Lifespan shutdown awaits all tracked tasks before closing outbound
    clients.
    """

    def __init__(self) -> None:
        """Initialize an empty relay tracker."""
        self._tasks: set[asyncio.Task[Any]] = set()

    def wrap(self, gen: AsyncIterator[str]) -> AsyncIterator[str]:
        """Wrap an async generator so its ASGI task lifecycle is tracked.

        The returned iterator behaves identically to ``gen``, but the
        ASGI streaming task is registered with the tracker on first
        iteration and auto-removed via ``add_done_callback``.
        """
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
        """Block until all active relays finish, with a 30-second timeout."""
        if not self._tasks:
            return
        try:
            async with asyncio.timeout(30.0):
                await asyncio.gather(*list(self._tasks), return_exceptions=True)
        except TimeoutError:
            pass


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown lifecycle."""
    # Startup: initialise shared state.
    _app.state.relays = ActiveRelays()
    yield
    # Shutdown: wait for in-flight SSE relays before closing outbound clients.
    await _app.state.relays.wait_all()


app = FastAPI(lifespan=lifespan)


@app.get("/healthz")
async def healthz() -> JSONResponse:
    """Health check endpoint."""
    return JSONResponse({"status": "ok"})


@app.post("/v1/chat/completions", response_model=None)
async def chat_completions(request: Request) -> JSONResponse | StreamingResponse:
    """Chat Completions API — relays OpenAI streaming responses as SSE.

    * Non-streaming (``stream=False``): returns a standard JSON response.
    * Streaming (``stream=True``): returns ``text/event-stream`` (SSE).

    Active SSE relays are tracked via ``ActiveRelays`` so that the lifespan
    shutdown waits for all in-flight relays before closing the outbound HTTP
    client.
    """
    body = await request.json()
    stream = body.get("stream", False)

    if stream:
        relays: ActiveRelays = request.app.state.relays

        async def _relay_stream() -> AsyncIterator[str]:
            """Relay OpenAI streaming chunks to the client as SSE.

            TODO(@primal-codex): Replace placeholder with actual OpenAI call.
            """
            # Placeholder: emit a single chunk then signal completion.
            yield (
                "data: {"
                '"id":"chatcmpl-xxx",'
                '"object":"chat.completion.chunk",'
                '"choices":[{"delta":{"content":"Hello"}}]'
                "}\n\n"
            )
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            relays.wrap(_relay_stream()),
            media_type="text/event-stream",
        )

    # Non-streaming response.
    return JSONResponse(
        {
            "id": "chatcmpl-xxx",
            "object": "chat.completion",
            "choices": [{"message": {"role": "assistant", "content": "Hello"}}],
        },
    )


def run_serve() -> None:
    """Start the FastAPI server with graceful shutdown on SIGINT/SIGTERM.

    Reads ``host`` and ``port`` from ``~/.primal-codex/config.toml``
    (``[server]`` section).  Falls back to ``127.0.0.1:8010`` when the
    config is absent or missing those keys.

    Uvicorn internally handles ``SIGINT`` and ``SIGTERM`` by draining active
    HTTP connections before exiting.  The lifespan context manager additionally
    waits for in-flight OpenAI SSE relays and closes the outbound HTTP client.
    """
    cfg = load_config()
    uvicorn_config = uvicorn.Config(
        app,
        host=cfg.server.host,
        port=cfg.server.port,
    )
    server = uvicorn.Server(uvicorn_config)
    server.run()
