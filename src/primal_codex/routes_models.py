"""List models route."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Request

if TYPE_CHECKING:
    from primal_codex.app_context import AppContext

from primal_codex.models import ModelInfo, ModelsResponse

router = APIRouter(tags=["models"])


@router.get(
    "/models",
    summary="List Models",
    description="Return metadata for all models discovered from configured providers.",
    operation_id="list_models",
)
def list_models(request: Request) -> ModelsResponse:
    """List all models — reads from pre-computed model info.

    Models are sorted alphabetically by provider ID, then by model ID
    within each provider, for a consistent display order.
    """
    ctx: AppContext = request.app.state.ctx
    flat: list[ModelInfo] = []
    for inner in ctx.model_map.values():
        flat.extend(inner.values())
    return ModelsResponse(models=flat)
