"""Health check route."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(tags=["system"])


@router.get(
    "/healthz",
    summary="Health Check",
    description="Returns a simple status to confirm the server is running.",
)
async def healthz() -> JSONResponse:
    """Health check endpoint."""
    return JSONResponse({"status": "ok"})
