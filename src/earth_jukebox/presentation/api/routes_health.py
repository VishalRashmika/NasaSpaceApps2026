"""Health endpoint (F-060)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from earth_jukebox.application.services import Services
from earth_jukebox.domain.mapping_version import MAPPING_VERSION
from earth_jukebox.presentation.api.dependencies import get_services
from earth_jukebox.presentation.api.schemas import HealthResponse

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(services: Annotated[Services, Depends(get_services)]) -> HealthResponse:
    """Return API health status and versions."""
    return HealthResponse(
        status="ok",
        version=services.version,
        mapping_version=MAPPING_VERSION,
    )
