"""Responses relay route."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Request

if TYPE_CHECKING:
    from fastapi.responses import JSONResponse, StreamingResponse

from primal_codex.responses import handle_responses

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
    """Relay upstream responses as JSON or SSE."""
    return await handle_responses(request)
