"""Unit tests for F-035 (Score round-trip decoder)."""

from __future__ import annotations

import numpy as np

from earth_jukebox.application.use_cases.round_trip import decode_score, fidelity_round_trip
from earth_jukebox.application.use_cases.sonify import sonify
from earth_jukebox.domain.models import (
    ColormapKind,
    GeoExtent,
    LegendSpec,
    RecoveryMode,
    RecoveryQuality,
    ScalarField,
    ScaleType,
    SonificationParams,
    VariableCategory,
)


def _make_field(kind: ColormapKind = ColormapKind.SEQUENTIAL) -> ScalarField:
    h, w = 100, 200
    vmin, vmax = 0.0, 50.0
    # Gradient field from west to east and north to south
    y, x = np.mgrid[0:h, 0:w]
    vals = vmin + (x / w) * (vmax - vmin) * 0.7 + (y / h) * (vmax - vmin) * 0.3
    # Add small missing data hole
    vals[10:20, 10:20] = np.nan

    legend = LegendSpec(
        vmin=vmin,
        vmax=vmax,
        units="K",
        label="Surface Temp",
        kind=kind,
        category=VariableCategory.TEMPERATURE,
        center=25.0 if kind is ColormapKind.DIVERGING else None,
        scale=ScaleType.LINEAR,
    )
    quality = RecoveryQuality(
        mean_delta_e=0.8,
        p95_delta_e=1.5,
        masked_fraction=0.01,
        lut_is_monotonic_in_lightness=True,
        confidence=0.95,
        mode=RecoveryMode.COLORBAR,
        warnings=(),
    )
    return ScalarField(
        values=vals,
        legend=legend,
        extent=GeoExtent(),
        quality=quality,
        source_hash="round_trip_fixture",
    )


def test_f035_ac1_round_trip_correlation_high() -> None:
    # AC1: on synthetic fixtures r >= 0.95 for the neutral skin
    field = _make_field()
    score = sonify(field, SonificationParams(n_bands=5, n_cols=48))

    r = fidelity_round_trip(field, score)
    assert r >= 0.95, f"Expected r >= 0.95, got {r:.4f}"


def test_f035_ac1_diverging_fixture_correlation() -> None:
    field = _make_field(kind=ColormapKind.DIVERGING)
    score = sonify(field, SonificationParams(n_bands=5, n_cols=48))

    r = fidelity_round_trip(field, score)
    assert r >= 0.95, f"Expected r >= 0.95 for diverging fixture, got {r:.4f}"


def test_f035_ac2_decoder_uses_only_score_data() -> None:
    # AC2: decoder uses only Score data (not the field)
    field = _make_field()
    score = sonify(field, SonificationParams(n_bands=5, n_cols=48))

    # decode_score takes only score as argument
    grid = decode_score(score)
    assert grid.shape == (5, 48)
    assert np.any(~np.isnan(grid))
    # Decoded values are within [vmin, vmax]
    valid = grid[~np.isnan(grid)]
    assert float(np.min(valid)) >= field.legend.vmin - 1e-4
    assert float(np.max(valid)) <= field.legend.vmax + 1e-4
