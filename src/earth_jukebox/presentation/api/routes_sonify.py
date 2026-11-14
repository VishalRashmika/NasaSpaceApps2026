"""Sonify endpoint (F-062)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from earth_jukebox.application.services import Services
from earth_jukebox.application.use_cases.audio_legend import legend_pitch_r
from earth_jukebox.application.use_cases.description import generate_description
from earth_jukebox.application.use_cases.round_trip import fidelity_round_trip
from earth_jukebox.application.use_cases.sonify import sonify
from earth_jukebox.domain.errors import NotFoundError
from earth_jukebox.domain.models import SonificationParams
from earth_jukebox.domain.skins.registry import get_skin
from earth_jukebox.domain.sonification.score_serde import score_to_dict
from earth_jukebox.presentation.api.dependencies import get_services
from earth_jukebox.presentation.api.routes_skins import SKIN_DESCRIPTIONS
from earth_jukebox.presentation.api.schemas import (
    FidelityResponse,
    SkinMetadataResponse,
    SonifyRequest,
    SonifyResponse,
)

router = APIRouter(prefix="/api", tags=["sonify"])


@router.post("/sonify", response_model=SonifyResponse)
def sonify_endpoint(
    req: SonifyRequest,
    services: Annotated[Services, Depends(get_services)],
) -> SonifyResponse:
    """Generate deterministic Score, description, and round-trip fidelity from analysis (F-062)."""
    if services.analysis_store is None:
        raise NotFoundError("Analysis store service unavailable")

    field = services.analysis_store.load(req.analysis_id)
    # Validates skin existence (raises NotFoundError if unknown)
    skin = get_skin(req.skin)

    params = SonificationParams(
        n_cols=req.n_cols,
        skin_id=skin.id,
    )

    score = sonify(field, params)
    description = generate_description(field)
    round_trip_r = fidelity_round_trip(field, score)
    legend_r = legend_pitch_r(field.legend, skin)

    skin_metadata = SkinMetadataResponse(
        id=skin.id,
        name=skin.name,
        scale_description=SKIN_DESCRIPTIONS.get(skin.id, f"{skin.name} musical skin."),
        provisional=skin.provisional,
    )

    return SonifyResponse(
        score=score_to_dict(score),
        description=description,
        fidelity=FidelityResponse(
            round_trip_r=round(float(round_trip_r), 4),
            legend_r=round(float(legend_r), 4),
        ),
        skin=skin_metadata,
    )
