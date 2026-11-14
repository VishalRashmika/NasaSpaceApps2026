"""Skin registry and shipped skins."""

from __future__ import annotations

from earth_jukebox.domain.skins.hindustani import HINDUSTANI_SKIN
from earth_jukebox.domain.skins.neutral import NEUTRAL_SKIN
from earth_jukebox.domain.skins.registry import get_skin, list_skins, register_skin
from earth_jukebox.domain.skins.sri_lankan import SRI_LANKAN_SKIN

__all__ = [
    "HINDUSTANI_SKIN",
    "NEUTRAL_SKIN",
    "SRI_LANKAN_SKIN",
    "get_skin",
    "list_skins",
    "register_skin",
]
