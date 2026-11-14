"""Colormap presets endpoint (F-003)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from earth_jukebox.application.services import Services
from earth_jukebox.presentation.api.dependencies import get_services
from earth_jukebox.presentation.api.schemas import ColormapResponse

router = APIRouter(prefix="/api", tags=["colormaps"])


@router.get("/colormaps", response_model=list[ColormapResponse])
def get_colormaps(
    services: Annotated[Services, Depends(get_services)],
) -> list[ColormapResponse]:
    """List available colormap presets with their kind (sequential/diverging)."""
    if services.colormap_catalog is None:
        return []

    results: list[ColormapResponse] = []
    for name in services.colormap_catalog.names():
        kind = services.colormap_catalog.kind(name).value
        results.append(ColormapResponse(name=name, kind=kind))
    return results
