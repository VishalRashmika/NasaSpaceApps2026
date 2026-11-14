"""Skins endpoint (F-067)."""

from __future__ import annotations

from fastapi import APIRouter

from earth_jukebox.domain.skins.registry import list_skins
from earth_jukebox.presentation.api.schemas import SkinResponse

router = APIRouter(prefix="/api", tags=["skins"])

SKIN_DESCRIPTIONS = {
    "neutral": "Major pentatonic scale with neutral scientific instruments.",
    "hindustani": "Hindustani classical raga scale with glides and ornaments.",
    "hindustani_malhar": "Hindustani classical raga scale with glides and ornaments.",
    "sri_lankan": "Traditional Sri Lankan scale and rhythm accompaniment.",
}


@router.get("/skins", response_model=list[SkinResponse])
def get_skins() -> list[SkinResponse]:
    """List available musical skins with scale cents and descriptions."""
    skins = list_skins()
    return [
        SkinResponse(
            id=s.id,
            name=s.name,
            provisional=s.provisional,
            scale_cents=list(s.scale_cents),
            description=SKIN_DESCRIPTIONS.get(s.id, f"{s.name} musical skin."),
        )
        for s in skins
    ]
