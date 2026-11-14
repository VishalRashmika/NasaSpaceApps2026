"""Unit tests for F-036 (Text description generator)."""

from __future__ import annotations

import numpy as np

from earth_jukebox.application.use_cases.description import generate_description
from earth_jukebox.domain.models import (
    ColormapKind,
    GeoExtent,
    LegendSpec,
    RecoveryMode,
    RecoveryQuality,
    ScalarField,
    ScaleType,
    VariableCategory,
)


def _make_field(
    confidence: float = 0.95,
    mode: RecoveryMode = RecoveryMode.COLORBAR,
    masked_fraction: float = 0.15,
) -> ScalarField:
    h, w = 50, 100
    vmin, vmax = -2.5, 30.0
    rng = np.random.default_rng(123)
    values = rng.uniform(vmin, vmax, size=(h, w))
    # Make tropics (band 2) western third highest
    values[20:30, 0:30] = vmax

    legend = LegendSpec(
        vmin=vmin,
        vmax=vmax,
        units="°C",
        label="Sea Surface Temperature",
        kind=ColormapKind.DIVERGING,
        category=VariableCategory.TEMPERATURE,
        center=14.0,
        scale=ScaleType.LINEAR,
    )
    quality = RecoveryQuality(
        mean_delta_e=1.0,
        p95_delta_e=2.0,
        masked_fraction=masked_fraction,
        lut_is_monotonic_in_lightness=True,
        confidence=confidence,
        mode=mode,
        warnings=(),
    )
    return ScalarField(
        values=values,
        legend=legend,
        extent=GeoExtent(),
        quality=quality,
        source_hash="desc_test_hash",
    )


def test_f036_ac1_deterministic_and_word_count() -> None:
    # AC1: deterministic; <= 120 words; contains units and min/max
    field = _make_field()
    desc1 = generate_description(field)
    desc2 = generate_description(field)
    assert desc1 == desc2

    words = desc1.split()
    assert len(words) <= 120
    assert "°C" in desc1
    assert "-2.5" in desc1
    assert "30.0" in desc1 or "30" in desc1
    assert "Sea Surface Temperature" in desc1
    assert "15%" in desc1 or "15.0%" in desc1


def test_f036_ac2_confidence_caveat() -> None:
    # AC2: includes literal phrase "approximate" when quality.confidence < 0.7
    field_low_conf = _make_field(confidence=0.65)
    desc = generate_description(field_low_conf)
    assert "approximate" in desc
    assert len(desc.split()) <= 120


def test_f036_ac2_luminance_fallback_caveat() -> None:
    # AC2: includes literal phrase "not data-faithful" for luminance fallback
    field_lum = _make_field(mode=RecoveryMode.LUMINANCE_FALLBACK, confidence=0.5)
    desc = generate_description(field_lum)
    assert "not data-faithful" in desc
    assert len(desc.split()) <= 120
