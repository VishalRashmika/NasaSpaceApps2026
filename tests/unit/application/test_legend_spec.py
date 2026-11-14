"""Tests for F-007: Legend metadata."""

from __future__ import annotations

import pytest

from earth_jukebox.application.use_cases.legend_metadata import build_legend_spec
from earth_jukebox.domain.errors import InvalidLegendError
from earth_jukebox.domain.models import ColormapKind, Orientation, ScaleType


def test_f007_ac1_invalid_metadata_raises() -> None:
    # F-007 AC1: vmin >= vmax, center outside range, unknown category,
    # log scale with vmin <= 0 -> InvalidLegendError.

    # 1. vmin >= vmax
    with pytest.raises(InvalidLegendError) as exc1:
        build_legend_spec(vmin=10.0, vmax=5.0, units="K", label="T", kind=ColormapKind.SEQUENTIAL)
    assert "vmin must be < vmax" in str(exc1.value)

    # 2. center outside range
    with pytest.raises(InvalidLegendError) as exc2:
        build_legend_spec(
            vmin=-5.0,
            vmax=5.0,
            units="K",
            label="T",
            kind=ColormapKind.DIVERGING,
            center=10.0,
        )
    assert "center" in str(exc2.value)

    # 3. unknown category
    with pytest.raises(InvalidLegendError) as exc3:
        build_legend_spec(
            vmin=0.0,
            vmax=10.0,
            units="K",
            label="T",
            kind=ColormapKind.SEQUENTIAL,
            category="invalid_cat",  # type: ignore[arg-type]
        )
    assert "category" in str(exc3.value)

    # 4. log scale with vmin <= 0
    with pytest.raises(InvalidLegendError) as exc4:
        build_legend_spec(
            vmin=0.0,
            vmax=10.0,
            units="K",
            label="T",
            kind=ColormapKind.SEQUENTIAL,
            scale=ScaleType.LOG,
        )
    assert "log" in str(exc4.value)


def test_f007_ac2_diverging_without_center_defaults_and_warns() -> None:
    # F-007 AC2: kind=DIVERGING without center -> center = midpoint,
    # and the response says so in warnings.
    legend, warnings = build_legend_spec(
        vmin=-10.0,
        vmax=30.0,
        units="°C",
        label="Temp Anomaly",
        kind=ColormapKind.DIVERGING,
        center=None,
        orientation=Orientation.HORIZONTAL,
    )
    assert legend.center == 10.0  # (-10 + 30) / 2
    assert "diverging_center_defaulted" in warnings
