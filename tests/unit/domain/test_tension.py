"""Unit tests for F-092: Inter-frame change -> harmonic tension."""

from __future__ import annotations

import numpy as np

from earth_jukebox.domain.models import (
    ColormapKind,
    GeoExtent,
    LegendSpec,
    RecoveryMode,
    RecoveryQuality,
    ScalarField,
)
from earth_jukebox.domain.skins import get_skin
from earth_jukebox.domain.sonification.tension import (
    compute_inter_frame_change_from_fields,
    compute_inter_frame_change_from_grids,
    compute_tension_drone,
)


def _make_field(values: np.ndarray) -> ScalarField:
    legend = LegendSpec(
        vmin=0.0,
        vmax=100.0,
        units="°C",
        label="Temperature",
        kind=ColormapKind.SEQUENTIAL,
    )
    extent = GeoExtent()
    quality = RecoveryQuality(
        mean_delta_e=0.1,
        p95_delta_e=0.2,
        masked_fraction=0.0,
        lut_is_monotonic_in_lightness=True,
        confidence=0.95,
        mode=RecoveryMode.COLORBAR,
    )
    return ScalarField(
        values=values,
        legend=legend,
        extent=extent,
        quality=quality,
        source_hash="test_hash",
    )


def test_inter_frame_change_identical_fields_ac1() -> None:
    """F-092 AC1: Identical fields produce 0.0 inter-frame change."""
    vals = np.full((10, 10), 50.0, dtype=np.float64)
    f1 = _make_field(vals)
    f2 = _make_field(vals.copy())

    change = compute_inter_frame_change_from_fields([f1, f2])
    assert change == 0.0

    # Single field also returns 0.0
    assert compute_inter_frame_change_from_fields([f1]) == 0.0


def test_inter_frame_change_varying_fields_ac1() -> None:
    """F-092 AC1: Fields with known shift produce exact mean normalized change."""
    v1 = np.full((10, 10), 20.0, dtype=np.float64)  # u = 0.2
    v2 = np.full((10, 10), 40.0, dtype=np.float64)  # u = 0.4
    v3 = np.full((10, 10), 50.0, dtype=np.float64)  # u = 0.5

    f1 = _make_field(v1)
    f2 = _make_field(v2)
    f3 = _make_field(v3)

    # Pair 1: |0.4 - 0.2| = 0.2
    # Pair 2: |0.5 - 0.4| = 0.1
    # Mean: 0.15
    change = compute_inter_frame_change_from_fields([f1, f2, f3])
    assert abs(change - 0.15) < 1e-6


def test_inter_frame_change_from_grids_ac1() -> None:
    """F-092 AC1: Grid computation works identically."""
    g1 = np.zeros((5, 48), dtype=np.float64)
    g2 = np.full((5, 48), 0.25, dtype=np.float64)

    change = compute_inter_frame_change_from_grids([g1, g2])
    assert abs(change - 0.25) < 1e-6


def test_tension_drone_zero_change_ac2() -> None:
    """F-092 AC2: When change == 0, drone is tonic + fifth without tension pitch."""
    neutral_skin = get_skin("neutral")
    pitches, tension = compute_tension_drone(neutral_skin, mean_change=0.0)

    # C3 (48) + G3 (55)
    assert pitches == (48.0, 55.0)
    assert tension is None


def test_tension_drone_positive_change_ac3() -> None:
    """F-092 AC3: When change > 0, tension pitch added proportional to skin tension cents."""
    # Neutral skin: tonic=48, fifth=55, tension_cents=200 (2 semitones: D3)
    neutral_skin = get_skin("neutral")

    # At full scale (change >= 0.25)
    pitches_full, tension_full = compute_tension_drone(neutral_skin, mean_change=0.30)
    assert tension_full is not None
    assert tension_full == 50.0  # 48 + 2.0 = 50.0 (D3)
    assert pitches_full == (48.0, 50.0, 55.0)

    # At partial scale (change = 0.125 -> half scale = 1.0 semitone)
    pitches_half, tension_half = compute_tension_drone(neutral_skin, mean_change=0.125)
    assert tension_half is not None
    assert tension_half == 49.0  # 48 + 1.0 = 49.0 (C#3)
    assert pitches_half == (48.0, 49.0, 55.0)


def test_tension_drone_hindustani_skin_ac3() -> None:
    """F-092 AC3: Hindustani skin uses tritone tension interval (600 cents)."""
    hindustani_skin = get_skin("hindustani")
    pitches, tension = compute_tension_drone(hindustani_skin, mean_change=0.25)

    assert tension is not None
    # 48 + 6.0 = 54.0 (F#3 / Tivra Ma)
    assert tension == 54.0
    assert pitches == (48.0, 54.0, 55.0)
