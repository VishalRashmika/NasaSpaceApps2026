"""Unit and property tests for F-025 (Local variability) and F-026 (Global variability / tempo)."""

from __future__ import annotations

import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st

from earth_jukebox.domain.sonification.variability import (
    compute_bpm,
    compute_local_variability,
)


def test_f025_ac1_flat_field_density_one() -> None:
    # AC1: a flat field gives density 1 everywhere
    grid_u = np.full((5, 48), 0.5, dtype=np.float64)
    coverage = np.ones((5, 48), dtype=np.float64)

    density, roughness = compute_local_variability(grid_u, coverage)
    assert np.all(density == 1)
    assert np.all(roughness == 0.0)


def test_f025_ac1_checkerboard_edges() -> None:
    # AC1: checkerboard / high contrast field gives density 4 at high gradient cells
    grid_u = np.zeros((5, 48), dtype=np.float64)
    # Put a block of 1s in the center surrounded by 0s
    grid_u[1:4, 10:20] = 1.0
    coverage = np.ones((5, 48), dtype=np.float64)

    density, roughness = compute_local_variability(grid_u, coverage)
    # The edges between 0 and 1 have high gradients and reach density 4
    assert np.any(density == 4)
    # Flat regions (e.g. far left) have density 1
    assert density[0, 0] == 1
    assert np.all(roughness >= 0.0)
    assert np.all(roughness <= 1.0)


def test_f025_ac2_percentiles_computed_on_valid_cells_only() -> None:
    # AC2: thresholds are the documented percentiles, computed over valid cells only
    grid_u = np.zeros((5, 10), dtype=np.float64)
    coverage = np.zeros((5, 10), dtype=np.float64)

    # Make only 4 cells valid with coverage 1.0
    coverage[0, 0:4] = 1.0
    grid_u[0, 0] = 0.0
    grid_u[0, 1] = 0.1
    grid_u[0, 2] = 0.4
    grid_u[0, 3] = 0.9

    density, _roughness = compute_local_variability(grid_u, coverage)
    # Valid cells have valid densities in {1, 2, 4}
    assert set(density[0, 0:4].tolist()).issubset({1, 2, 4})
    # Invalid cells produce density 0
    assert np.all(density[1:, :] == 0)


def test_f026_ac_tempo_bounds_and_monotone() -> None:
    # AC: constant field -> 72 bpm; maximal-variance field -> 120
    coverage = np.ones((5, 48), dtype=np.float64)

    # Constant field
    flat_u = np.full((5, 48), 0.5, dtype=np.float64)
    assert compute_bpm(flat_u, coverage) == 72.0

    # Max variance field (half 0, half 1 -> std = 0.5 >= 0.3)
    max_u = np.zeros((5, 48), dtype=np.float64)
    max_u[:, :24] = 1.0
    assert compute_bpm(max_u, coverage) == 120.0

    # Intermediate field
    mid_u = flat_u.copy()
    mid_u[0, 0] = 1.0
    bpm_mid = compute_bpm(mid_u, coverage)
    assert 72.0 < bpm_mid < 120.0


@settings(max_examples=50)
@given(
    scale_factor=st.floats(min_value=0.0, max_value=1.0),
    scale_factor_higher=st.floats(min_value=0.0, max_value=1.0),
)
def test_f026_ac_property_monotone_in_std(scale_factor: float, scale_factor_higher: float) -> None:
    # Property test: monotonic in std
    s1 = min(scale_factor, scale_factor_higher)
    s2 = max(scale_factor, scale_factor_higher)

    coverage = np.ones((4, 4), dtype=np.float64)
    base_pattern = np.array(
        [
            [0.0, 1.0, 0.0, 1.0],
            [1.0, 0.0, 1.0, 0.0],
            [0.0, 1.0, 0.0, 1.0],
            [1.0, 0.0, 1.0, 0.0],
        ]
    )
    # Centered pattern with mean 0.5 and varying std
    u1 = 0.5 + (base_pattern - 0.5) * s1
    u2 = 0.5 + (base_pattern - 0.5) * s2

    bpm1 = compute_bpm(u1, coverage)
    bpm2 = compute_bpm(u2, coverage)
    assert bpm1 <= bpm2
