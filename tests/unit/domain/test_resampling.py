"""Unit and property tests for F-020 (Field resampling to grid)."""

from __future__ import annotations

import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st

from earth_jukebox.domain.sonification.resampling import resample_field


def test_f020_ac1_constant_field() -> None:
    # AC1: constant field -> constant grid; coverage 1
    h, w = 100, 240
    const_val = 42.0
    arr = np.full((h, w), const_val, dtype=np.float64)

    grid = resample_field(arr, n_bands=5, n_cols=48)
    assert grid.means.shape == (5, 48)
    assert grid.coverage.shape == (5, 48)
    assert np.allclose(grid.means, const_val)
    assert np.allclose(grid.coverage, 1.0)


def test_f020_ac2_half_nan_field() -> None:
    # AC2: field with half NaN -> coverage 0.5 and mean unaffected by NaN
    h, w = 50, 100
    val = 15.5
    arr = np.full((h, w), val, dtype=np.float64)
    # Set top half of every cell to NaN or alternating rows to NaN
    arr[::2, :] = np.nan

    grid = resample_field(arr, n_bands=5, n_cols=48)
    assert np.allclose(grid.means, val)
    assert np.allclose(grid.coverage, 0.5)


@settings(max_examples=50)
@given(
    h=st.integers(min_value=10, max_value=80),
    w=st.integers(min_value=10, max_value=80),
    n_bands=st.integers(min_value=2, max_value=8),
    n_cols=st.integers(min_value=2, max_value=16),
)
def test_f020_ac3_property_grid_mean_within_bounds(
    h: int, w: int, n_bands: int, n_cols: int
) -> None:
    # AC3: property test (hypothesis): grid mean in [field min, field max]
    rng = np.random.default_rng(42)
    # Generate random floats and introduce some NaNs
    arr = rng.uniform(low=-10.0, high=50.0, size=(h, w))
    mask = rng.random(size=(h, w)) < 0.2
    arr[mask] = np.nan

    valid_vals = arr[~np.isnan(arr)]
    if len(valid_vals) == 0:
        return

    f_min = float(np.min(valid_vals))
    f_max = float(np.max(valid_vals))

    grid = resample_field(arr, n_bands=n_bands, n_cols=n_cols)
    valid_means = grid.means[~np.isnan(grid.means)]
    if len(valid_means) > 0:
        assert float(np.min(valid_means)) >= f_min - 1e-6
        assert float(np.max(valid_means)) <= f_max + 1e-6
    assert np.all(grid.coverage >= 0.0)
    assert np.all(grid.coverage <= 1.0)
