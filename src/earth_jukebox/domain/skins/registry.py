"""F-050: Skin registry.

Pure data skin registry. get_skin(id), list_skins(), register_skin(skin).
"""

from __future__ import annotations

from collections.abc import Sequence

from earth_jukebox.domain.errors import NotFoundError
from earth_jukebox.domain.models import Skin
from earth_jukebox.domain.skins.hindustani import HINDUSTANI_SKIN
from earth_jukebox.domain.skins.neutral import NEUTRAL_SKIN
from earth_jukebox.domain.skins.sri_lankan import SRI_LANKAN_SKIN

_REGISTRY: dict[str, Skin] = {
    NEUTRAL_SKIN.id: NEUTRAL_SKIN,
    HINDUSTANI_SKIN.id: HINDUSTANI_SKIN,
    SRI_LANKAN_SKIN.id: SRI_LANKAN_SKIN,
}

_ALIASES: dict[str, str] = {
    "hindustani_malhar": "hindustani",
}


def register_skin(skin: Skin) -> None:
    """Register a skin in the global registry."""
    if not skin.scale_cents:
        raise ValueError(f"Skin {skin.id} has empty scale_cents")
    if skin.scale_cents[0] != 0.0:
        raise ValueError(f"Skin {skin.id} scale_cents[0] must be 0.0, got {skin.scale_cents[0]}")
    for i in range(len(skin.scale_cents) - 1):
        if not skin.scale_cents[i] < skin.scale_cents[i + 1]:
            raise ValueError(f"Skin {skin.id} scale_cents must be strictly ascending")
    if any(c < 0.0 or c >= 1200.0 for c in skin.scale_cents):
        raise ValueError(f"Skin {skin.id} scale_cents must be in [0.0, 1200.0)")

    _REGISTRY[skin.id] = skin


def get_skin(skin_id: str) -> Skin:
    """Get a skin by ID. Raises NotFoundError if unknown."""
    resolved_id = _ALIASES.get(skin_id, skin_id)
    if resolved_id not in _REGISTRY:
        raise NotFoundError(f"Unknown skin id: '{skin_id}'")
    return _REGISTRY[resolved_id]


def list_skins() -> Sequence[Skin]:
    """List all registered skins sorted by id."""
    return tuple(_REGISTRY[k] for k in sorted(_REGISTRY.keys()))
