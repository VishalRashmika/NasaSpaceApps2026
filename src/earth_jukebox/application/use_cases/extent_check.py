"""Geo-extent and projection verification (F-010).

Verifies whether a map region matches an equirectangular projection within aspect ratio tolerance.
"""

from __future__ import annotations

from earth_jukebox.domain.models import GeoExtent


def check_extent(
    extent: GeoExtent,
    map_width: int,
    map_height: int,
    mismatch_threshold: float = 0.15,
) -> tuple[str, ...]:
    """Check GeoExtent against map aspect ratio (F-010).

    Returns:
        tuple of warning strings (e.g. ("projection_unverified",))
    """
    warnings: list[str] = []

    # 1. Projection check
    if extent.projection.lower() != "equirectangular":
        warnings.append("projection_unverified")
        return tuple(warnings)

    # 2. Aspect ratio comparison
    if map_width <= 0 or map_height <= 0:
        warnings.append("projection_unverified")
        return tuple(warnings)

    d_lon = extent.lon_max - extent.lon_min
    d_lat = extent.lat_max - extent.lat_min
    if d_lat <= 0 or d_lon <= 0:
        warnings.append("projection_unverified")
        return tuple(warnings)

    extent_aspect = d_lon / d_lat
    map_aspect = float(map_width) / float(map_height)

    ratio_mismatch = abs(map_aspect - extent_aspect) / extent_aspect
    if ratio_mismatch > mismatch_threshold:
        warnings.append("projection_unverified")

    return tuple(warnings)
