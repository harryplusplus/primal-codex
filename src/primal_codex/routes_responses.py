"""Responses relay route."""

from __future__ import annotations

import json
from http import HTTPStatus
from typing import TYPE_CHECKING

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import ValidationError

if TYPE_CHECKING:
    from primal_codex.app_context import AppContext

from primal_codex.responses import (
    ResponsesApiRequest,
    relay_stream,
)

router = APIRouter()


@router.post(
    "/responses",
    response_model=None,
    summary="Relay Responses Request",
    description=(
        "Accepts an OpenAI Responses API request body and relays it to"
        " the appropriate provider as a Chat Completions request."
    ),
)
async def responses(
    request: Request,
) -> JSONResponse | StreamingResponse:
    """Handle a ``POST /responses`` request.

    Parses and validates the request body with Pydantic, then streams
    the relayed response as server-sent events.

    Args:
        request: The incoming FastAPI request.

    Returns:
        A ``StreamingResponse`` for valid streaming requests, or a
        ``JSONResponse`` error otherwise.

    """
    try:
        raw = await request.json()
    except json.JSONDecodeError as e:
        return JSONResponse(
            {"error": f"Invalid JSON in request body: {e}"},
            status_code=HTTPStatus.BAD_REQUEST,
        )

    try:
        body = ResponsesApiRequest.model_validate(raw)
    except ValidationError as e:
        return JSONResponse(
            {"error": f"Invalid request body: {e}"},
            status_code=HTTPStatus.BAD_REQUEST,
        )

    if not body.stream:
        return JSONResponse(
            {"error": "Only streaming responses are supported."},
            status_code=HTTPStatus.BAD_REQUEST,
        )

    ctx: AppContext = request.app.state.ctx
    provider_id, _, model_id = body.model.partition("/")
    if (
        not provider_id
        or not model_id
        or provider_id not in ctx.model_map
        or model_id not in ctx.model_map[provider_id]
    ):
        return JSONResponse(
            {"error": f"Model not found: {body.model}"},
            status_code=HTTPStatus.BAD_REQUEST,
        )

    provider = ctx.primal_config.providers.get(provider_id)
    if provider is None:
        return JSONResponse(
            {"error": f"Provider not found for model: {body.model}"},
            status_code=HTTPStatus.BAD_REQUEST,
        )

    api_key = provider.resolve_api_key()

    return StreamingResponse(
        relay_stream(body, model_id, provider.base_url, api_key),
        media_type="text/event-stream",
        headers={
            "cache-control": "no-cache",
            "x-accel-buffering": "no",
        },
    )
