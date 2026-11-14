"""Unit tests for F-021 (Normalisation & centre handling)."""

from __future__ import annotations

import math

import numpy as np

from earth_jukebox.domain.models import ColormapKind, LegendSpec, ScaleType
from earth_jukebox.domain.sonification.normalization import denormalize_u, normalize_value


def test_f021_ac1_ac2_sequential_linear() -> None:
    # AC1 & AC2: vmin->0, vmax->1, monotonic, clamping
    legend = LegendSpec(
        vmin=10.0,
        vmax=50.0,
        units="K",
        label="Temp",
        kind=ColormapKind.SEQUENTIAL,
        scale=ScaleType.LINEAR,
    )
    assert normalize_value(10.0, legend) == 0.0
    assert normalize_value(50.0, legend) == 1.0
    assert normalize_value(30.0, legend) == 0.5

    # AC2: Clamping outside bounds
    assert normalize_value(5.0, legend) == 0.0
    assert normalize_value(60.0, legend) == 1.0

    # Monotonicity
    vals = [5.0, 10.0, 20.0, 30.0, 45.0, 50.0, 100.0]
    u_vals = [normalize_value(v, legend) for v in vals]
    assert all(u_vals[i] <= u_vals[i + 1] for i in range(len(u_vals) - 1))

    # Round trip
    for v in [10.0, 20.0, 30.0, 45.0, 50.0]:
        u = normalize_value(v, legend)
        assert math.isclose(denormalize_u(u, legend), v, rel_tol=1e-5)


def test_f021_ac1_diverging_centre() -> None:
    # AC1: centre -> 0.5 (diverging), monotonic non-decreasing
    legend = LegendSpec(
        vmin=-10.0,
        vmax=30.0,
        center=0.0,
        units="C",
        label="Anomaly",
        kind=ColormapKind.DIVERGING,
        scale=ScaleType.LINEAR,
    )
    assert normalize_value(-10.0, legend) == 0.0
    assert normalize_value(30.0, legend) == 1.0
    assert normalize_value(0.0, legend) == 0.5
    assert normalize_value(-5.0, legend) == 0.25
    assert normalize_value(15.0, legend) == 0.75

    # Clamping
    assert normalize_value(-20.0, legend) == 0.0
    assert normalize_value(50.0, legend) == 1.0

    # Monotonicity
    vals = [-15.0, -10.0, -5.0, 0.0, 10.0, 30.0, 40.0]
    u_vals = [normalize_value(v, legend) for v in vals]
    assert all(u_vals[i] <= u_vals[i + 1] for i in range(len(u_vals) - 1))

    # Round trip
    for v in [-10.0, -5.0, 0.0, 15.0, 30.0]:
        u = normalize_value(v, legend)
        assert math.isclose(denormalize_u(u, legend), v, rel_tol=1e-5)


def test_f021_ac3_scale_log() -> None:
    # AC3: scale=LOG normalises in log10 space (u of geometric mean = 0.5)
    vmin = 1.0
    vmax = 100.0
    geom_mean = math.sqrt(vmin * vmax)  # 10.0
    legend = LegendSpec(
        vmin=vmin,
        vmax=vmax,
        units="ppm",
        label="Aerosol",
        kind=ColormapKind.SEQUENTIAL,
        scale=ScaleType.LOG,
    )
    assert normalize_value(1.0, legend) == 0.0
    assert normalize_value(100.0, legend) == 1.0
    assert math.isclose(normalize_value(geom_mean, legend), 0.5, abs_tol=1e-6)

    # Values <= 0 treated as vmin
    assert normalize_value(0.0, legend) == 0.0
    assert normalize_value(-5.0, legend) == 0.0

    # Round trip
    for v in [1.0, 5.0, 10.0, 50.0, 100.0]:
        u = normalize_value(v, legend)
        assert math.isclose(denormalize_u(u, legend), v, rel_tol=1e-5)


def test_f021_array_support() -> None:
    legend = LegendSpec(
        vmin=-5.0,
        vmax=5.0,
        center=0.0,
        units="deg",
        label="Anom",
        kind=ColormapKind.DIVERGING,
    )
    arr = np.array([[-5.0, 0.0, 5.0], [np.nan, -2.5, 2.5]], dtype=np.float64)
    u_arr = normalize_value(arr, legend)
    assert np.isclose(u_arr[0, 0], 0.0)
    assert np.isclose(u_arr[0, 1], 0.5)
    assert np.isclose(u_arr[0, 2], 1.0)
    assert np.isnan(u_arr[1, 0])
    assert np.isclose(u_arr[1, 1], 0.25)
    assert np.isclose(u_arr[1, 2], 0.75)
