"""Tests for recover_field use case."""

from __future__ import annotations

import numpy as np

from earth_jukebox.application.use_cases.recover_field import recover_field
from earth_jukebox.domain.models import GeoExtent, Orientation
from earth_jukebox.infrastructure.colormaps.catalog import MatplotlibColormapCatalog
from earth_jukebox.infrastructure.vision.decoder import PillowImageDecoder
from earth_jukebox.infrastructure.vision.recoverer import VisionFieldRecoverer
from earth_jukebox.infrastructure.vision.synthetic import generate_map


def test_recover_field_end_to_end() -> None:
    png, truth_field, legend, cbar_box, map_box = generate_map(
        cmap="viridis",
        seed=42,
        orientation=Orientation.HORIZONTAL,
    )
    decoder = PillowImageDecoder()
    decoded = decoder.decode(png)

    catalog = MatplotlibColormapCatalog()
    recoverer = VisionFieldRecoverer(catalog)

    field = recover_field(
        image=decoded,
        field_recoverer=recoverer,
        vmin=legend.vmin,
        vmax=legend.vmax,
        units=legend.units,
        label=legend.label,
        kind=legend.kind,
        colorbar_box=cbar_box,
        map_box=map_box,
    )

    assert field.legend.label == legend.label
    assert field.quality.confidence >= 0.9

    # Compare recovered values against truth
    truth = truth_field.values
    valid = (~np.isnan(truth)) & (~np.isnan(field.values))
    rmse = np.sqrt(np.mean((field.values[valid] - truth[valid]) ** 2))
    pct = rmse / (legend.vmax - legend.vmin) * 100.0
    assert pct <= 2.0


def test_recover_field_aspect_mismatch_warning() -> None:
    # 1:1 map with global (2:1) extent -> projection_unverified warning
    png, _truth_field, legend, _cbar_box, map_box = generate_map(
        cmap="viridis",
        seed=1,
    )
    decoder = PillowImageDecoder()
    decoded = decoder.decode(png)

    catalog = MatplotlibColormapCatalog()
    recoverer = VisionFieldRecoverer(catalog)

    # 1:1 extent (lat -90..90, lon -90..90 -> aspect 1.0) on 2:1 map (aspect 2.0)
    extent_1to1 = GeoExtent(lat_min=-90, lat_max=90, lon_min=-90, lon_max=90)

    field = recover_field(
        image=decoded,
        field_recoverer=recoverer,
        vmin=legend.vmin,
        vmax=legend.vmax,
        units=legend.units,
        label=legend.label,
        kind=legend.kind,
        colorbar_box=None,
        map_box=map_box,
        preset_name="viridis",
        extent=extent_1to1,
    )

    assert "projection_unverified" in field.quality.warnings
