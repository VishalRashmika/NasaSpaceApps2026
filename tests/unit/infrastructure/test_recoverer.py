"""Tests for FieldRecoverer and F-013 (Luminance fallback)."""

from __future__ import annotations

import numpy as np

from earth_jukebox.domain.models import (
    ColormapKind,
    DecodedImage,
    LegendSpec,
    RecoveryMode,
)
from earth_jukebox.infrastructure.colormaps.catalog import MatplotlibColormapCatalog
from earth_jukebox.infrastructure.vision.recoverer import VisionFieldRecoverer
from earth_jukebox.infrastructure.vision.synthetic import generate_map


def test_f013_ac1_grayscale_gradient_monotonic() -> None:
    # F-013 AC1: grayscale gradient recovers monotonic values.
    # Create horizontal grayscale ramp from 0 to 255
    ramp = np.tile(np.linspace(0, 255, 256, dtype=np.uint8), (50, 1))
    rgb = np.stack([ramp, ramp, ramp], axis=-1)

    decoded = DecodedImage(
        rgb=rgb,
        content_hash="dummy_hash",
        original_width=256,
        original_height=50,
    )
    legend = LegendSpec(
        vmin=0.0,
        vmax=100.0,
        units="units",
        label="Luminance Test",
        kind=ColormapKind.SEQUENTIAL,
    )

    catalog = MatplotlibColormapCatalog()
    recoverer = VisionFieldRecoverer(catalog)

    field = recoverer.recover(
        image=decoded,
        legend=legend,
        map_box=None,
        colorbar_box=None,
        preset_name=None,
    )

    # First row values should be strictly monotonic non-decreasing
    row = field.values[25, :]
    assert np.all(np.diff(row) >= 0.0)
    assert row[0] < row[-1]


def test_f013_ac2_not_data_faithful_warning_and_confidence_cap() -> None:
    # F-013 AC2: warning is present in ScalarField.quality and confidence capped at 0.3.
    ramp = np.tile(np.linspace(0, 255, 100, dtype=np.uint8), (50, 1))
    rgb = np.stack([ramp, ramp, ramp], axis=-1)
    decoded = DecodedImage(
        rgb=rgb,
        content_hash="dummy",
        original_width=100,
        original_height=50,
    )
    legend = LegendSpec(
        vmin=0.0,
        vmax=10.0,
        units="m",
        label="Test",
        kind=ColormapKind.SEQUENTIAL,
    )

    catalog = MatplotlibColormapCatalog()
    recoverer = VisionFieldRecoverer(catalog)

    field = recoverer.recover(
        image=decoded,
        legend=legend,
        map_box=None,
        colorbar_box=None,
        preset_name=None,
    )

    assert field.quality.mode == RecoveryMode.LUMINANCE_FALLBACK
    assert field.quality.confidence <= 0.3
    assert "not_data_faithful" in field.quality.warnings


def test_recoverer_preset_mode() -> None:
    # Test recovery using PRESET mode
    png, _field, legend, _cbox, mbox = generate_map(cmap="viridis", seed=1)
    # decode image
    from earth_jukebox.infrastructure.vision.decoder import PillowImageDecoder

    decoder = PillowImageDecoder()
    decoded = decoder.decode(png)

    catalog = MatplotlibColormapCatalog()
    recoverer = VisionFieldRecoverer(catalog)

    field = recoverer.recover(
        image=decoded,
        legend=legend,
        map_box=mbox,
        colorbar_box=None,
        preset_name="viridis",
    )

    assert field.quality.mode == RecoveryMode.PRESET
    assert field.quality.confidence >= 0.8
    assert field.values.shape == (mbox.h, mbox.w)
