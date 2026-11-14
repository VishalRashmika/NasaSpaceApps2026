"""Tests for F-011: Recovery quality report."""

from __future__ import annotations

import numpy as np

from earth_jukebox.application.use_cases.quality import (
    compute_quality,
    is_lut_monotonic_in_lightness,
)
from earth_jukebox.domain.models import RecoveryMode


def test_f011_ac2_confidence_formula_boundaries() -> None:
    # F-011 AC2: confidence formula implemented exactly as documented; unit-tested at boundaries.

    # 1. Perfect recovery (mean_de=0, masked_fraction=0, COLORBAR) -> 1.0
    values = np.zeros((10, 10))
    dists = np.zeros((10, 10))
    q = compute_quality(
        values=values,
        distances=dists,
        mode=RecoveryMode.COLORBAR,
        lut_is_monotonic_in_lightness=True,
        map_width=500,
    )
    assert q.mean_delta_e == 0.0
    assert q.p95_delta_e == 0.0
    assert q.masked_fraction == 0.0
    assert q.confidence == 1.0
    assert not q.warnings

    # 2. mean_de = 10 (f_de = 0), masked_fraction = 0 -> base = 0.6*0 + 0.4*1 = 0.4
    dists_10 = np.full((10, 10), 10.0)
    q2 = compute_quality(
        values=values,
        distances=dists_10,
        mode=RecoveryMode.COLORBAR,
        lut_is_monotonic_in_lightness=True,
        map_width=500,
    )
    assert abs(q2.confidence - 0.4) < 1e-6
    assert "high_color_distance" in q2.warnings

    # 3. PRESET mode factor (0.9)
    q_preset = compute_quality(
        values=values,
        distances=dists,
        mode=RecoveryMode.PRESET,
        lut_is_monotonic_in_lightness=True,
        map_width=500,
    )
    assert abs(q_preset.confidence - 0.9) < 1e-6

    # 4. LUMINANCE_FALLBACK capped at 0.3 and warns not_data_faithful
    q_lum = compute_quality(
        values=values,
        distances=dists,
        mode=RecoveryMode.LUMINANCE_FALLBACK,
        lut_is_monotonic_in_lightness=True,
        map_width=500,
    )
    assert q_lum.confidence == 0.3
    assert "not_data_faithful" in q_lum.warnings

    # 5. projection_unverified multiplier (0.8)
    q_proj = compute_quality(
        values=values,
        distances=dists,
        mode=RecoveryMode.COLORBAR,
        lut_is_monotonic_in_lightness=True,
        map_width=500,
        extra_warnings=("projection_unverified",),
    )
    assert abs(q_proj.confidence - 0.8) < 1e-6
    assert "projection_unverified" in q_proj.warnings

    # 6. low_resolution warning (< 200 px)
    q_low_res = compute_quality(
        values=values,
        distances=dists,
        mode=RecoveryMode.COLORBAR,
        lut_is_monotonic_in_lightness=True,
        map_width=150,
    )
    assert "low_resolution" in q_low_res.warnings


def test_f011_ac1_synthetic_vs_wrong_preset() -> None:
    # F-011 AC1: perfect synthetic recovery -> confidence >= 0.9;
    # map recovered with wrong preset -> confidence < 0.5 and warning "high_color_distance".

    # Good recovery: low distance, little masking
    values = np.zeros((100, 100))
    dists = np.full((100, 100), 0.5)
    q_good = compute_quality(
        values=values,
        distances=dists,
        mode=RecoveryMode.COLORBAR,
        lut_is_monotonic_in_lightness=True,
        map_width=500,
    )
    assert q_good.confidence >= 0.9

    # Wrong preset: high distance (e.g. mean_de = 8.0) and high masking (85% NaN)
    values_bad = np.zeros((100, 100))
    values_bad[:85, :] = np.nan
    dists_bad = np.full((100, 100), 8.0)
    q_bad = compute_quality(
        values=values_bad,
        distances=dists_bad,
        mode=RecoveryMode.PRESET,
        lut_is_monotonic_in_lightness=True,
        map_width=500,
    )
    assert q_bad.confidence < 0.5
    assert "high_color_distance" in q_bad.warnings


def test_f011_lut_lightness_monotonicity() -> None:
    # Monotonic increasing
    lab_inc = np.zeros((5, 3))
    lab_inc[:, 0] = [10.0, 25.0, 50.0, 75.0, 90.0]
    assert is_lut_monotonic_in_lightness(lab_inc)

    # Monotonic with +- 1.0 noise
    lab_noise = np.zeros((5, 3))
    lab_noise[:, 0] = [10.0, 25.0, 24.5, 75.0, 90.0]  # 24.5 is >= 25.0 - 1.0
    assert is_lut_monotonic_in_lightness(lab_noise)

    # Non-monotonic (e.g. rainbow / diverging like turbo or RdBu_r)
    lab_rainbow = np.zeros((5, 3))
    lab_rainbow[:, 0] = [10.0, 80.0, 30.0, 85.0, 20.0]
    assert not is_lut_monotonic_in_lightness(lab_rainbow)
