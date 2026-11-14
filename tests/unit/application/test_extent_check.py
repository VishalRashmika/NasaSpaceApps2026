"""Tests for F-010: Geo-extent & unsupported-projection warning."""

from __future__ import annotations

from earth_jukebox.application.use_cases.extent_check import check_extent
from earth_jukebox.domain.models import GeoExtent


def test_f010_ac1_aspect_ratio_and_projection_warning() -> None:
    # F-010 AC1: 2:1 image with global extent -> no warning;
    # 1:1 image with global extent -> warning.
    global_extent = GeoExtent(lat_min=-90.0, lat_max=90.0, lon_min=-180.0, lon_max=180.0)

    # 2:1 image (e.g. 1024x512) with global extent
    warnings_2to1 = check_extent(global_extent, map_width=1024, map_height=512)
    assert "projection_unverified" not in warnings_2to1

    # 1:1 image (e.g. 512x512) with global extent
    warnings_1to1 = check_extent(global_extent, map_width=512, map_height=512)
    assert "projection_unverified" in warnings_1to1


def test_f010_non_equirectangular_projection_warning() -> None:
    globe_extent = GeoExtent(
        lat_min=-90.0,
        lat_max=90.0,
        lon_min=-180.0,
        lon_max=180.0,
        projection="orthographic",
    )
    warnings = check_extent(globe_extent, map_width=1024, map_height=512)
    assert "projection_unverified" in warnings
