from __future__ import annotations

import pytest

from earth_jukebox.domain.models import (
    ColormapKind,
    GeoExtent,
    LegendSpec,
    PixelBox,
)


def test_legend_rejects_inverted_range() -> None:
    with pytest.raises(ValueError):
        LegendSpec(vmin=1, vmax=0, units="K", label="x", kind=ColormapKind.SEQUENTIAL)


def test_legend_effective_center_defaults_to_midpoint() -> None:
    lg = LegendSpec(vmin=-2, vmax=4, units="C", label="x", kind=ColormapKind.DIVERGING)
    assert lg.effective_center == 1.0
    lg2 = LegendSpec(vmin=-2, vmax=4, units="C", label="x", kind=ColormapKind.DIVERGING, center=0)
    assert lg2.effective_center == 0


def test_pixelbox_rejects_empty() -> None:
    with pytest.raises(ValueError):
        PixelBox(0, 0, 0, 5)


def test_geoextent_rejects_inverted() -> None:
    with pytest.raises(ValueError):
        GeoExtent(lat_min=10, lat_max=-10)
