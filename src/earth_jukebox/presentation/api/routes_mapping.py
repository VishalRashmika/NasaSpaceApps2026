"""Mapping manifest endpoint (F-064)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from earth_jukebox.application.use_cases.mapping_manifest import describe_mapping

router = APIRouter(prefix="/api", tags=["mapping"])


@router.get("/mapping")
def get_mapping() -> dict[str, Any]:
    """Expose fixed mapping manifest (docs/06 tables and rules) for the UI."""
    return describe_mapping()
